// the socketio instance
"use strict";

//let default_url = "http://r2lab.inria.fr:999/";
let devel_url = "http://localhost:10000/";
let prod_url = "https://r2lab.inria.fr:999/";
let default_url = devel_url;

let socket = undefined;

let sections = {
    phones: {depth: 2,  def_request: 'REQUEST',
	     def_send: '[{"id":1, "airplane_mode":"on"}]',
	     prettifier: pretty_records,
	    },
    nodes : {depth: 10, def_request: 'REQUEST',
	     def_send: '[{"id":1, "available":"ko"}]',
	     prettifier: pretty_records,
	    },
    leases: {depth: 2,  def_request: 'REQUEST',
	     def_send: '-- not recommended --',
	     prettifier: pretty_leases,
	    },
}

//////////////////// global functions
function show_connected(url) {
    $("#connection_status").css("background-color", "green");
    $("#connection_status").html("connected to " + url);
}
function show_disconnected() {
    $("#connection_status").css("background-color", "gray");
    $("#connection_status").html("idle");
}
function show_failed_connection(url) {
    $("#connection_status").css("background-color", "red");
    $("#connection_status").html("connection failed to " + url);
}    

function connect_sidecar(url) {
    if (socket) {
	pause();
    }
    console.log("Connecting to sidecar at " + url);
    socket = io.connect(url);
// this 'connected' thing probably is asynchroneous..
//    if ( ! socket.connected) {
//	show_failed_connection(url);
//	socket = undefined;
//	return;
//    } 

    show_connected(url);
    
    for (let name in sections) {
	// behaviour for the apply buttons
	$(`div#request-${name}>button`).click(function(e){
	    send(name, 'request:', 'request-');
	});
	$(`div#send-${name}>button`).click(function(e){
	    send(name, 'info:', 'send-');
	});
	// what to do upon reception on that channel
	let channel = 'info:' + name;
	console.log(`subscribing to channel ${channel}`)
	socket.on(channel, function(msg){
	    console.log(`received on channel ${channel} : ${msg}`);
	    update_contents(name, msg)});
    }
}

////////////////////
let set_url = function(e) {
    let url = $('input#url').val();
    if (url == "") {
	url = default_url;
	$('input#url').val(url);
    }
    connect_sidecar(url);
}

let pause = function() {
    console.log("Pausing");
    if (socket == undefined) {
	console.log("already paused");
	return;
    }
    socket.disconnect();
    socket = undefined;
    show_disconnected();
}

let set_devel_url = function(e) {
    $('input#url').val(devel_url);
    pause();
    set_url();
}

let set_prod_url = function(e) {
    $('input#url').val(prod_url);
    pause();
    set_url();
}
//////////////////// the 3 channels
// a function to prettify the leases message
function pretty_leases(json) {
    let leases = $.parseJSON(json);
    let html = "<ul>";
    leases.forEach(function(lease) {
	html +=
	    `<li>${lease.slicename} from ${lease.valid_from} until ${lease.valid_until}</li>`
    })
    html += "</ul>";
    return html;
}

// applicable to nodes and phones
function pretty_records(json) {
    let records = $.parseJSON(json);
    let html = "<ul>";
    records.forEach(function(record) {
	html += `<li>${JSON.stringify(record)}</li>`;
    });
    html += "</ul>";
    return html;
}

// update the 'contents' <ul> and keep at most <depth> entries in there
function update_contents(name, value) {
    let ul_sel = `#ul-${name}`;
    let $ul = $(ul_sel);
    let details = value;
    let prettifier = sections[name].prettifier;
    if (prettifier)
	details = prettifier(details);
    let html = `<li><span class="date">${new Date()}</span>${details}</li>`;
    let depth = sections[name].depth;
    let lis = $(`${ul_sel}>li`);
    if (lis.length >= depth) {
	lis.first().remove()
    }
    $(ul_sel).append(html);
}

let clear_all = function() {
    for (let name in sections) {
	$(`#ul-${name}`).html("");
    }
}

    
let populate = function() {
    for (let name in sections) {
	// create form for the request input
	let html;
	html = "";
	html += `<div class="allpage" id="request-${name}">`;
	html += `<span class="header"> send Request ${name}</span>`;
	html += `<input id="${name}" /><button class="green">Request update</button>`;
	html += `</div>`;
	html += `<div class="allpage" id="send-${name}">`;
	html += `<span class="header">send raw (json) line as ${name}</span>`;
	html += `<input class="wider" id="send-${name}" /><button class="red">Send json</button>`;
	html += `</div>`;
	$("#controls").append(html);
	html = "";
	html += `<div class="contents" id="contents-${name}">`;
	html += `<h3>Contents of ${name}</h3>`;
	html += `<ul class="contents" id="ul-${name}"></ul>`;
	html += `</div>`;
	$("#contents").append(html);
	$(`div#send-${name}>input`).val(sections[name].def_send);
	$(`div#request-${name}>input`).val(sections[name].def_request);
    }
};

// channel_prefix is typically 'info:' or 'request:'
// widget_prefix is either 'send-' or 'request-'
function send(name, channel_prefix, widget_prefix) {
    let channel = channel_prefix + name ;
    let value = $('#' + widget_prefix + name + ">input").val();
    console.log("emitting on channel " + channel + " : <" + value + ">");
    socket.emit(channel, value);
    return false;
}
    
////////////////////
$(() => {populate(); set_url();})
