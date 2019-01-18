// a sidecar client for the new websockets implementation
"use strict";

//let default_url = "http://r2lab.inria.fr:999/";
let devel_url = "ws://localhost:10000/";
let prod_url = "wss://r2lab.inria.fr:999/";
let default_url = prod_url;
// tmp
    default_url = devel_url;

let websocket = undefined;

let sections = {
    nodes : {depth: 10, def_request: '"REQUEST"',
             def_info: '[{"id":1, "available":"ko"}]',
             prettifier: pretty_records,
            },
    phones: {depth: 2,  def_request: '"REQUEST"',
             def_info: '[{"id":1, "airplane_mode":"on"}]',
             prettifier: pretty_records,
            },
    leases: {depth: 2,  def_request: '"REQUEST"',
             def_info: '-- not recommended --',
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
    if (websocket) {
        disconnect();
    }
    console.log("Connecting to sidecar at " + url);
    websocket = new WebSocket(url)
    show_connected(url);
    for (let category in sections) {
        // behaviour for the apply buttons
        $(`div#request-${category}>button`).click(function(e){
            send(category, 'request', 'request-');
        });
        $(`div#info-${category}>button`).click(function(e){
            send(category, 'info', 'info-');
        });
    }
    websocket.onmessage = function(event) {
        let umbrella = JSON.parse(event.data);
        console.log(`ws: incoming umbrella ${umbrella}`)
        let category = umbrella.category;
        let action = umbrella.action;
        let message = umbrella.message;
        if (action == "info") {
            update_contents(category, message);
        }
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

let disconnect = function() {
    if (websocket == undefined) {
        console.log("already disconnected");
        return;
    }
    console.log("disconnecting")
    websocket.close();
    websocket = undefined;
    show_disconnected();
}

let set_devel_url = function(e) {
    $('input#url').val(devel_url);
    disconnect();
    set_url();
}

let set_prod_url = function(e) {
    $('input#url').val(prod_url);
    disconnect();
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
    let details = JSON.stringify(value);
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
        html += `<input id="request-${name}" /><button class="green">Request update</button>`;
        html += `</div>`;
        html += `<div class="allpage" id="info-${name}">`;
        html += `<span class="header">send raw (json) line as ${name}</span>`;
        html += `<input class="wider" id="info-${name}" /><button class="red">Send json</button>`;
        html += `</div>`;
        html += `<hr/>`;
        $("#controls").append(html);
        html = "";
        html += `<div class="contents" id="contents-${name}">`;
        html += `<h3>Contents of ${name}</h3>`;
        html += `<ul class="contents" id="ul-${name}"></ul>`;
        html += `<hr/>`;
        html += `</div>`;
        $("#contents").append(html);
        $(`div#info-${name}>input`).val(sections[name].def_info);
        $(`div#request-${name}>input`).val(sections[name].def_request);
    }
};

function send(category, action, widget_prefix) {
    let umbrella = {category: category, action: action};
    let selector = `input#${widget_prefix}${category}`;
    let strmessage = $(selector).val();
    console.log(`selector=${selector}`, `strmessage`, strmessage);
    let objmessage = JSON.parse(strmessage);
    umbrella.message = objmessage;
    console.log(`emitting on category ${category} action ${action}`, umbrella);
    let json=JSON.stringify(umbrella);
    console.log(`json`, json);
    websocket.send(json);
    return false;
}

////////////////////
$(() => {populate(); set_url();})
