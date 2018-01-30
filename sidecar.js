#!/usr/bin/env node
"use strict";

//// oct. 2016
// major changes in channels naming scheme
// with the addition of the 'phones' channels
// see AA-overview.md for detail
//
// another major change is about sidecar only sending along CHANGES
// as compared to its current known state

// xxx : the option version (when run with -l) should probably
// need to use http instead of https for devel mode..

// dependencies
const fs = require('fs');
//const path = require('path');
const url = require('url');
const express = require('express');
const http = require('http');
const https = require('https');
const socketio = require('socket.io');


////////// globals
// use -v to turn on
let verbose_flag = false;
// use -l to turn on
let local_flag = false;
// default is to be incremental - i.e. emit only differences
// use -c (--complete) to go back to the mode where the complete
// news string gets emitted
let incremental_flag = true;

let default_url = "https://r2lab.inria.fr:999/";
let default_devel_url = "http://localhost:10000/";
let global_url = undefined;

let default_ssl_key = "/etc/pki/tls/private/r2lab.inria.fr.key";
let global_ssl_key = undefined;

let default_ssl_cert = "/etc/pki/tls/certs/r2lab_inria_fr.crt";
let global_ssl_cert = undefined;

// locate and load certificates
function ssl_cert_options() {
    try {
	// the production box
	// load the installed SSL certs for r2lab as defined in httpd config
	// see file /etc/httpd/conf.d/r2lab.vhost
	return {
	    key  : fs.readFileSync(global_ssl_key),
	    cert : fs.readFileSync(global_ssl_cert),
	}
    } catch (err) {
	console.log(`Could not load SSL material : ${err}`);
	process.exit(1);
    }
}

//////// names for the channels used are
// info:nodes
// request:nodes
// info:phones
// request:phones
// info:leases
// request:leases

// filenames used for persistent channels : essentially for smooth restart
// /var/lib/sidecar/nodes.json
// /var/lib/sidecar/phones.json
// it is fine to delete, it will just take some while to rebuild itself
// from the outcome of monitor
// in local mode (for devel) these files are in current directory


// always display
function display() {
    for (let i in arguments) {
       console.log(`${new Date()} sidecar `, arguments[i]);
    }
}
// display only if in verbose mode
function vdisplay() {
    if (verbose_flag)
	display.apply(this, arguments);
}

// in the following, name = 'nodes' or 'phones' or 'leases' 
function info_channel_name(name) {
    return `info:${name}`;
}
function request_channel_name(name) {
    return `request:${name}`;
}
function db_filename(name) {
    if (! local_flag) {
	return `/var/lib/sidecar/${name}.json`;
    } else {
	return `./${name}.json`;
    }
}

////////////////////
function clean_dbfile(filename) {
    sync_save_dbfile(filename, []);
}



function initialize_socketio(io) {
    
// remainings of a socket.io example; this is only
// marginally helpful to check for the server sanity
io.on('connection', function(socket){
    display('user connect');
    socket.on('disconnect', function(){
	display('user disconnect');
    });
});

// this code is common to the 2 channels associated
// to persistent data (nodes and phones)
// when receiving something on a status channel (that is, either nodes or phones), we
// * update nodes.json (i.e, read the file, apply changes, store again)
// * and then, according to incremental_mode, we:
//   * either forward the news as-is if incremental_mode is off
//   * or forward the smallest delta that describes the changes if it is on
function prepare_persistent_channel(socket, name) {
    let info_channel = info_channel_name(name);
    let filename = db_filename(name);
    vdisplay(`arming callback for channel ${info_channel}`);
    socket.on(info_channel, function(news_string) {
	vdisplay(`received on channel ${info_channel} chunk ${news_string}`)
	let infos_to_emit = update_dbfile_from_news(filename, news_string, incremental_flag);
	// avoid the noise of sending empty news
	if (infos_to_emit.length >= 1) {
	    let string_to_emit = JSON.stringify(infos_to_emit);
	    io.emit(info_channel, string_to_emit);
	    vdisplay(`emitting on ${info_channel} chunk ${string_to_emit}`);
	    display(`emitting on ${info_channel} ${infos_to_emit.length} chunks`);
	} else {
	    vdisplay(`no news found in news_string (was ${news_string.length} chars long)`);
	}
    });
    // this now is how complete status gets transmitted initially
    let request_channel = request_channel_name(name);
    vdisplay(`arming callback for channel ${request_channel}`);
    socket.on(request_channel, function(msg) {
	display(`Received ${msg} on channel ${request_channel}`);
	// feature : if we can find 'CLEAR' in the text, we clear our own db
	if (msg.indexOf('CLEAR') != -1) {
	    clean_dbfile(filename);
	} 
	emit_file(io, filename, info_channel);
    });
}

// non-persistent channels are simpler,
// e.g. we always propagate a complete list of leases
function prepare_non_persistent_channel(socket, name) {
    let info_channel = info_channel_name(name);
    vdisplay(`arming callback for channel ${info_channel}`);
    socket.on(info_channel, function(infos){
	io.emit(info_channel, infos);
	let json = JSON.parse(infos);
	display(`Forwarding ${json.length} items on non-persistent channel ${info_channel}`);
    });

    let request_channel = request_channel_name(name);
    vdisplay(`arming callback for channel ${request_channel}`);
    socket.on(request_channel, function(anything) {
	display(`Forwarding trigger message ${anything} on channel ${request_channel}`);
	io.emit(request_channel, anything);
    });
    
}

// arm callbacks for the channels we use
io.on('connection', function(socket){
    //////////////////// (nodes) status
    prepare_persistent_channel(socket, 'nodes');

    //////////////////// phones
    prepare_persistent_channel(socket, 'phones');

    //////////////////// leases
    prepare_non_persistent_channel(socket, 'leases');

});

}

// convenience function to synchroneously read a file as a string
function sync_read_file_as_string(filename){
    try {
	let contents = fs.readFileSync(filename, 'utf8');
	vdisplay(`sync read ${filename} -> ${contents.length} chars`);
	if (! contents) {
	    display(`${filename}: WARNING, could not read`);
	    // artificially return an empty list
	    return "[]";
	} else {
	    return contents;
	}
    } catch(err){
	display(`${filename}: could not read - ${err}`);
	return "[]";
    }
}

// same but do JSON.parse on result
function sync_read_file_as_infos(filename) {
    try {
	return JSON.parse(sync_read_file_as_string(filename));
    } catch(err) {
	display(`${filename}: could not parse JSON - ${err}`);
	// return an empty list in this case
	// useful for when the file does not exist yet
	// a little hacky as this assumes all our files contain JSON lists
	return [];
    }
}

// utility to open a file and broadcast its contents on channel
function emit_file(io, filename, channel){
    let complete_string = sync_read_file_as_string(filename);
    if (complete_string) {
	vdisplay(`emit_file: sending on channel ${channel}:${complete_string.length} chars`);
	io.emit(channel, complete_string);
    } else {
	display(`OOPS - not emitting - empty contents found in ${filename}`)
    }
}

// convenience function to save a list of JS infos (records) into a file
// we do everything synchroneously to avoid trouble
function sync_save_dbfile(filename, infos){
    try {
	let contents = JSON.stringify(infos);
	fs.writeFileSync(filename, contents, 'utf8');
	vdisplay(`sync (over)wrote ${contents.length} on ${filename}`)
    } catch(err) {
	display(`${filename}: could not sync write ${filename} - ${err}`);
    }
}

// convenience function to
// (*) open and read the complete status file - e.g. nodes.json
// (*) merge new info into that dictionary
// (*) save result in same file
// (*) return object is the infos to be broadcasted
//   (*) if incremental_mode == false (traditional mode)
//       this is essentially (the infos for) news_string as-is
//   (*) if incremental_mode == true,
//       only the changes to the db are reported
function update_dbfile_from_news(filename, news_string, incremental_mode) {
    if (news_string == "") {
	display("OOPS - empty news feed - ignoring");
	return [];
    }
    try {
	// start from the complete infos
	let complete_infos = sync_read_file_as_infos(filename);
	// convert string into infos
	let news_infos = JSON.parse(news_string);
	vdisplay(`updating dbfile with ${news_infos.length} news infos`);
	// merge both and save in file
	let delta_infos = merge_news_into_complete(complete_infos, news_infos, filename);
	// xxx
	return incremental_mode ? delta_infos : news_infos;
    } catch(err) {
	display(` OOPS - unexpected exception in update_dbfile_from_news`,
		`news_string was ${news_string}`,
		`strack trace is ${err.stack}`);
	return [];
    }
}

// merge news info into complete infos
// save complete infos if filename is provided
// return delta_infos, the smallest set of infos
// that describe the changes from previous db state
function merge_news_into_complete(complete_infos, news_infos, filename) {
    let delta_infos = [];
    news_infos.forEach(function(news_info) {
	let id = news_info.id;
	let item_already_present_in_db = false;
	complete_infos.forEach(function(complete_info) {
	    // search for corresponding item in complete db
	    if (complete_info['id'] == id) {
		item_already_present_in_db = true;
		let items_has_changes = false;
		let delta_info;
		// copy all contents from news_info into complete_infos
		for (let prop in news_info) {
		    // do we have change for that node x prop
		    if ( (news_info[prop] != undefined) &&
			 (complete_info[prop] != news_info[prop]) ) {
			// is this the first change detected for that node
			if ( ! items_has_changes) {
			    items_has_changes = true;
			    delta_info = { 'id' : id };
			    delta_infos.push(delta_info);
			}
			// check if we need to create a delta_info 
			complete_info[prop] = news_info[prop];
			delta_info[prop] = news_info[prop];
		    }
		}
		// we're done searching for this item
		// skip rest of search in complete_infos
		return;
	    }
	})
	// complete gets created empty at the very beginning
	// so, if id is not yet known, add it as-is
	if (! item_already_present_in_db) {
	    complete_infos.push(news_info);
	    delta_infos.push(news_info);
	}
    })
    if (filename) {
	sync_save_dbfile(filename, complete_infos);
    }

    return delta_infos;
}

////////////////////////////////////////
let usage = `Usage: sidecar.js [options][-v] [-l] [-c] [-u (http|https)://hostname:port/]\n\
  -v: verbose mode \n\
  -l: local mode for devel : create local logfile, and change SSL defaults \n\
  -c: complete mode - default is to incremental mode, i.e. publish differences;\n\
      complete floods with the whole data \n\
  -u: (http|https)://hostname:port/\n\
      set url (hostname ignored)  - def is ${default_url}\n\
  -C: path for the local SSL cert - def is ${default_ssl_cert}\n\
  -K: path for the local SSL key  - def is ${default_ssl_key}`;  

function parse_args() {
    // very rough parsing of command line args - to set verbosity
    let argv = process.argv.slice(2);
    for (let index=0; index < argv.length; index++) {
	let arg = argv[index];
	if (arg == "-v") {
	    verbose_flag = true;
	} else if (arg == "-l") {
	    // local / devel  (use json files and logs in .)
	    local_flag = true;
	    default_ssl_cert = "localhost.crt";
	    default_ssl_key  = "localhost.key";
	    default_url = default_devel_url;
	} else if (arg == "-c") {
	    incremental_flag = false;
	} else if (arg == "-u") {
	    global_url = argv[index+1];
	    index ++;
	} else if (arg == "-C") {
	    global_ssl_cert = argv[index+1];
	    index ++;
	} else if (arg == "-K") {
	    global_ssl_key = argv[index+1];
	    index ++;
	} else {
	    console.log(usage);
	    process.exit(1);
	} 
    }
    global_url = (global_url || default_url);
    global_ssl_cert = (global_ssl_cert || default_ssl_cert);
    global_ssl_key = (global_ssl_key || default_ssl_key);
    
    display(`======== using URL = ${global_url}`);
    vdisplay("==========");
    vdisplay(`SSL cert file = ${global_ssl_cert}`);
    vdisplay(`SSL cert key = ${global_ssl_key}`);
    vdisplay("==========");
    display(`complete file for nodes = ${db_filename('node')}`);
    display(`complete file for phones = ${db_filename('phone')}`);
    
}

// run http server
function run_server() {
    process.on('SIGINT', function(){
	display("Received SIGINT - exiting"); process.exit(1);});
    process.on('SIGTERM', function(){
	display("Received SIGTERM - exiting"); process.exit(1);});


    // https://nodejs.org/docs/latest/api/url.html
    let url_obj = url.parse(global_url);
    let scheme = url_obj.protocol || 'http:' ;      // "http:" or "https:"
    let hostname = url_obj.hostname || 'localhost';
    let port = url_obj.port || '80';
    port = parseInt(port);
    vdisplay(`scheme = ${scheme}, hostname = ${hostname}, port = ${port}`);

    let express_app = express();
    let server;
    if (scheme == 'https:') {
	vdisplay("using https stack");
	let server_https = https.createServer(ssl_cert_options(), express_app);
	server = server_https;
    } else {
	vdisplay("using http stack");
	let server_http = http.Server(express_app);
	server = server_http;
    }

    process.on('uncaughtException',
	       function(err) {console.log(`async. execption ->${err}`); })

    try {
	let io = socketio(server);
	initialize_socketio(io);
	server.listen(port, function(){
	    display(`listening on ${global_url} (hostname ignored)`);
	    display(`verbose flag is ${verbose_flag}`);
	    display(`local flag is ${local_flag}`);
	    display(`incremental mode is ${incremental_flag}`);
	});
    } catch (err) {
	console.log(`Could not run http server on port ${port}`);
	console.log(`Need to sudo ?`);
	console.log(err);
    }
}

function main() {
    parse_args();
    run_server();
}

main()
