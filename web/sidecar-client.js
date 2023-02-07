// a sidecar client for the new websockets implementation
"use strict"

let devel_url = "ws://localhost:10000/"
let prod_url = "wss://r2lab-sidecar.inria.fr:443/";
let default_url = devel_url

let websocket = undefined

////////////////////
let categories = {
    nodes : {depth: 10, def_request: '"PLEASE"',
             def_info: '[{"id":1, "available":"ko"}]',
             prettifier: pretty_records,
            },
    phones: {depth: 5,  def_request: '"PLEASE"',
             def_info: '[{"id":1, "airplane_mode":"on"}]',
             prettifier: pretty_records,
            },
    pdus: {depth: 5, def_request: '"PLEASE"',
            def_info: '[{"id": "jaguar", "on_off": "on"}]',
            prettifier: pretty_records,
            },
    leases: {depth: 2,  def_request: '"PLEASE"',
             def_info: '-- not recommended --',
             prettifier: pretty_leases,
            },
}

//let actions = {
//    request: {color: "red", button: "Request update"},
//    info : {color: "green", button: "Send (json) data"},
//}


let populate = function() {
    $("input#url")
        .keypress(function(ev) {
            var keycode = (ev.keyCode ? ev.keyCode : ev.which)
            if (keycode == '13')
                set_url()
        })
    let anchor = $("#separator-controls")
    function add_element(newdiv) {
        anchor.after(newdiv)
        anchor = newdiv
        return newdiv
    }
    for (let category in categories) {
        // insert in the right order, for tabindexes to work as expected
        add_element(
            $(`<div>`, {id: `${category}-label`, style: `grid-area:${category}-label`})
            .html(`${category}`))

        // request button - send button - input area
        let buttons = add_element(
            $(`<div>`, {id: `${category}-buttons`, style: `grid-area:${category}-buttons`})
            .addClass("category-buttons"))
        // create button
        buttons.append(
                $(`<button>`, {id: `${category}-request`})
                .html("request update")
                .addClass(`red`))
        // set its behaviour
        $(`#${category}-request`).click((e) => send(category, "request"))

        // create 2nd button
        buttons.append(
            $(`<button>/`, {id: `${category}-info`})
            .html('send data')
            .addClass(`green`))
        // set its behaviour
        $(`#${category}-info`).click((e) => send(category, 'info'))

        buttons.append(
            $(`<input />`, {id: `${category}-input`})
            .val(`${categories[category].def_info}`)
            .keypress(function (ev) {
                let keycode = (ev.keyCode ? ev.keyCode : ev.which)
                if (keycode == '13')
                    send(category, 'info')
            })
        )


        // contents area
        $(`#top-contents`).append(
            $(`<div>`,
              {id: `${category}-contents`,
               class: "contents",
               style: `grid-area: ${category}-contents`})
                .html(`${category}`)
                .append(
                    $(`<ul>`,
                      {id: `ul-${category}`, class: "contents"}))
        )
        $("button").attr('tabindex', -1)
    }
}


//////////////////// global functions
function set_status(text, color) {
    $("#connection-status").css("background-color", color).html(text)
}

function update_status() {
    let color
    let text
    if (websocket === undefined) {
        color = "gray"
        text = "idle"
    } else switch (websocket.readyState) {
        case websocket.OPEN:
            color = "green"
            text = `connected to ${websocket.url}`
            break
        case websocket.OPEN:
            color = "green"
            text = `connected to ${websocket.url}`
            break
        case websocket.CONNECTING:
            color = "orange"
            text = `connecting to ${websocket.url}`
            break
        default:
            color = "red"
            text = `connection closed to ${websocket.url}`
    }
    set_status(text, color)
}


function cyclic_update() {
    setTimeout(function () {
        update_status()
        cyclic_update()
    }, 1000)
}

cyclic_update()



function show_connected(url) {
    $("#connection-status").css("background-color", "green")
    $("#connection-status").html("connected to " + url)
}
function show_disconnected(message) {
    $("#connection-status").css("background-color", "gray")
    $("#connection-status").html(message)
}
function show_failed_connection(url) {
    $("#connection-status").css("background-color", "red")
    $("#connection-status").html("connection failed to " + url)
}

function connect_sidecar(url) {
    if (websocket) {
        disconnect()
    }
    console.log(`Connecting to sidecar at ${url}`)
    websocket = new WebSocket(url)
    set_status("connecting ..", "orange")

    // ignore events that do not target the current websocket instance
    // this may happen typically when reconnecting, we close and immediately
    // re-open, but the close event comes back referring to the previous connection
    websocket.onopen = function(event) {
        if (event.target != websocket)
            return
        update_status()
    }
    websocket.onclose = function(event) {
        if (event.target != websocket)
            return
        websocket = undefined
        update_status()
    }

    websocket.onmessage = function(event) {
        if (event.target != websocket)
            return
        console.log("receiving message on websocket", websocket)
        let umbrella = JSON.parse(event.data)
        console.log(`websockets: incoming umbrella`, umbrella)
        let category = umbrella.category
        let action = umbrella.action
        let message = umbrella.message
        if (action == "info") {
            update_contents(category, message)
        }
    }
}


////////////////////
let set_url = function(e) {
    let url = $('input#url').val()
    if (url == "") {
        url = default_url
        $('input#url').val(url)
    }
    connect_sidecar(url)
}

let disconnect = function() {
    if (websocket == undefined) {
        console.log("already disconnected")
        return
    }
    console.log("disconnecting")
    websocket.close()
    websocket = undefined
    show_disconnected("idle")
}

let set_devel_url = function(e) {
    $('input#url').val(devel_url)
    disconnect()
    set_url()
}

let set_prod_url = function(e) {
    $('input#url').val(prod_url)
    disconnect()
    set_url()
}
//////////////////// the 3 channels
let pad2 = (number) => number.toString().padStart(2, 0)
function prettyDate() {
    let now = new Date()
    return `${pad2(now.getHours())}:`
    + `${pad2(now.getMinutes())}:`
    + `${pad2(now.getSeconds())}`
}

// a function to prettify the leases message
function pretty_leases(records) {
    records.sort((r1, r2) => r1.valid_from.localeCompare(r2.valid_from))
    let bullets = $(`<div>`).addClass('records')
    console.log(records)
    records.forEach(function(lease) {
        try {
            let [datef, timef] = lease.valid_from.split("T")
            let [dateu, timeu] = lease.valid_until.split("T")
            let inside = $(`<ul>`)
                .append($("<li>").html(`From ${datef}`))
                .append($("<li>").html(`at ${timef}`))
                .append($("<li>").html(`Until ${dateu}`))
                .append($("<li>").html(`at ${timeu}`))

            bullets.append(
                $(`<span>`)
                .addClass('record')
                .html(lease.slicename)
                .tooltip({title: inside, html: true}))
        } catch (e) {
            bullets.append(
                $(`<span>`)
                .addClass('record')
                .addClass('red')
                .html(`Unexpected lease ${lease}`)
            )
        }
    })
    return bullets
}

// applicable to nodes and phones
function pretty_records(records) {
    records.sort((r1, r2) => r1.id - r2.id)
    let bullets = $(`<div>`)
        .addClass('records')
    records.forEach(function(record) {
        let inside = $(`<ul>`)
        for (let attribute of Object.keys(record).sort())
            inside.append($(`<li>`).html(`"${attribute}" : ${JSON.stringify(record[attribute])}`))
        let color_class =
            ((record['available'] == 'ko')
             || (record['airplane_mode'] == 'fail')) ? "red" : ""
        bullets.append(
            $(`<span>`)
                .addClass('record')
                .addClass(color_class)
                .html(record.id)
                .tooltip({title: inside, html: true}))
    })
    return bullets
}

// update the 'contents' <ul> and keep at most <depth> entries in there
function update_contents(name, value) {
    let ul_sel = `#ul-${name}`
    let $ul = $(ul_sel)
    let prettifier = categories[name].prettifier
    let pretty = prettifier(value)
    let item = $(`<li>`)
        .append($(`<span class="date">${prettyDate()}</span>`)
                .append(pretty))

    let depth = categories[name].depth
    let lis = $(`${ul_sel}>li`)
    console.log(`trimming to ${depth} from ${lis.length}`)
    if (lis.length >= depth) {
        lis.last().remove()
    }
    $(ul_sel).prepend(item)
}

let clear_all = function() {
    for (let name in categories) {
        $(`#ul-${name}`).html("")
    }
}


function send(category, action) {
    let umbrella = {category: category, action: action}
    let strmessage
    if (action == "request")
        strmessage = '"PLEASE"'
    else {
        let selector = `#${category}-input`
        strmessage = $(selector).val()
    }
    console.log(`send strmessage=${strmessage}`)
    let objmessage = JSON.parse(strmessage)
    umbrella.message = objmessage
    console.log(`emitting on category ${category} action ${action}`, umbrella)
    let json = JSON.stringify(umbrella)
    websocket.send(json)
    return false
}

////////////////////
$(() => {
    populate()
    set_url()
    let tooltips = $('[data-toggle="tooltip"]')
    tooltips.tooltip()
    set_prod_url()
})
