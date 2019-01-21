// a sidecar client for the new websockets implementation
"use strict";

//let default_url = "http://r2lab.inria.fr:999/";
let devel_url = "ws://localhost:10000/";
let prod_url = "wss://r2lab.inria.fr:999/";
let default_url = prod_url;
// tmp
    default_url = devel_url;

let websocket = undefined;

////////////////////
let categories = {
    nodes : {depth: 10, def_request: '"PLEASE"',
             def_info: '[{"id":1, "available":"ko"}]',
             prettifier: pretty_records,
            },
    phones: {depth: 2,  def_request: '"PLEASE"',
             def_info: '[{"id":1, "airplane_mode":"on"}]',
             prettifier: pretty_records,
            },
    leases: {depth: 2,  def_request: '"PLEASE"',
             def_info: '-- not recommended --',
             prettifier: pretty_leases,
            },
}

let actions = {
    info : {color: "green", button: "Send (json) data"},
    request: {color: "red", button: "Request update"},
}
    

let populate = function() {
    let areas = ['button', 'input'];
    for (let category in categories) {
        // the label are - spans 2 lines of the grid
        $("#separator-controls").after(
            $(`<div>`, {id: `${category}-label`,
                        style: `grid-area:${category}-label`,
                       }).html(`${category}`));
        // the 4 grid items for input / button and info / request
        for (let action in actions) {
            for (let area of areas) {
                $("#separator-controls").after(
                    $("<div>", {id: `${category}-${action}-${area}`,
                                style: `grid-area:${category}-${action}-${area}`,
                               }));
            }
            // create button
            $(`#${category}-${action}-button`).append(
                $(`<button>${actions[action].button}</button>`)
                    .addClass(`${actions[action].color}`));
            // set its behaviour
            $(`div#${category}-${action}-button>button`).click(function(e){
                send(category, action);
            });
        }
        $(`#${category}-info-input`).append(
            $(`<input />`).val(`${categories[category].def_info}`));
        $(`#${category}-request-input`).append(
            $(`<input />`).val(`${categories[category].def_request}`));
        // contents area
        $(`#separator-contents`).after(
            $(`<div>`,
              {id: `${category}-contents`,
               class: "contents",
               style: `grid-area: ${category}-contents`})
                .html(`Contents of ${category}`)
                .append(
                    $(`<ul>`,
                      {id: `ul-${category}`, class: "contents"}))
        );
    }
}


//////////////////// global functions
function set_status(text, color) {
    $("#connection-status").css("background-color", color).html(text);
}    

function update_status() {
    let color;
    let text;
    if (websocket === undefined) {
        color = "gray";
        text = "idle";
    } else switch (websocket.readyState) {
        case websocket.OPEN:
            color = "green";
            text = `connected to ${websocket.url}`;
            break;
        case websocket.OPEN:
            color = "green";
            text = `connected to ${websocket.url}`;
            break;
        case websocket.CONNECTING:
            color = "orange";
            text = `connecting to ${websocket.url}`;
            break;
        default:
            color = "red";
            text = `connection closed to ${websocket.url}`;
    }
    set_status(text, color);
}


function cyclic_update() {
    setTimeout(function () {
        update_status();
        cyclic_update();
    }, 1000);
}

cyclic_update();
            
        

function show_connected(url) {
    $("#connection-status").css("background-color", "green");
    $("#connection-status").html("connected to " + url);
}
function show_disconnected(message) {
    $("#connection-status").css("background-color", "gray");
    $("#connection-status").html(message);
}
function show_failed_connection(url) {
    $("#connection-status").css("background-color", "red");
    $("#connection-status").html("connection failed to " + url);
}

function connect_sidecar(url) {
    if (websocket) {
        disconnect();
    }
    console.log(`Connecting to sidecar at ${url}`);
    websocket = new WebSocket(url);
    set_status("connecting ..", "orange");

    // ignore events that do not target the current websocket instance
    // this may happen typically when reconnecting, we close and immediately
    // re-open, but the close event comes back referring to the previous connection
    websocket.onopen = function(event) {
        if (event.target != websocket)
            return;
        update_status();
    }
    websocket.onclose = function(event) {
        if (event.target != websocket)
            return;
        websocket = undefined;
        update_status();
    }

    websocket.onmessage = function(event) {
        if (event.target != websocket)
            return;
        console.log("receiving message on websocket", websocket);
        let umbrella = JSON.parse(event.data);
        console.log(`websockets: incoming umbrella`, umbrella)
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
    show_disconnected("idle");
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
    let prettifier = categories[name].prettifier;
    if (prettifier)
        details = prettifier(details);
    let html = `<li><span class="date">${new Date()}</span>${details}</li>`;
    let depth = categories[name].depth;
    let lis = $(`${ul_sel}>li`);
    if (lis.length >= depth) {
        lis.first().remove()
    }
    $(ul_sel).append(html);
}

let clear_all = function() {
    for (let name in categories) {
        $(`#ul-${name}`).html("");
    }
}


function send(category, action) {
    let umbrella = {category: category, action: action};
    let selector = `div#${category}-${action}-input>input`;
    let strmessage = $(selector).val();
    let objmessage = JSON.parse(strmessage);
    umbrella.message = objmessage;
    console.log(`emitting on category ${category} action ${action}`, umbrella);
    let json = JSON.stringify(umbrella);
    websocket.send(json);
    return false;
}

////////////////////
$(() => {populate(); set_url();})
