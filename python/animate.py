#!/usr/bin/env python3

import random
import json
import time
import datetime

from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from sidecar_client import connect_url

# in seconds
default_cycle = 1
default_runs = 0

# should maybe default to this official one, but mostly it's firewalled
# default_sidecar_url = "https://r2lab.inria.fr:999/"
default_sidecar_url = "http://localhost:10000/"

node_ids = range(1, 38)
default_max_nodes_impacted = 10

######## helper to create float ranges
def drange(start, stop, step):
    result = []
    r = start
    while r < stop:
        result.append(r)
        r += step
    return result

######## valid values for initializing
nodes_field_possible_values = {
    'available' : [ None, 'ko'] + 3*['ok'],
    'cmc_on_off' : [ 'fail' ] + 3 * [ 'on', 'off' ],
    'control_ping' : [ 'on', 'off' ],
    'control_ssh' : ['on', 'off'],
    'os_release' : [ 'fedora-21', 'ubuntu-15.04', 'other', ],
    'gnuradio_release' : ['3.7.10', '', None],
    'uname' : [ 'foo', '4.2.300-generic' ],
    'image_radical' : [ 'ubuntu-15.04', 'oai-scrambler', '', None ],
    'usrp_type' : 12 * [ None ] + [ 'b210', 'n210', 'usrp1', 'usrp2'],
    'usrp_on_off' : 3 * ['on'] + ['off'],
    'usrp_duplexer' : ['none', 'for eNB', 'for UE'],
    'images_usrp' : [ [], ['usrp1.png'], ['usrp1.png', 'usrp2.jpg']],
    'images_wifi' : [ [], ['wifi1.png'], ['wifi1.png', 'wifi2.jpg']],
}

phones_field_possible_values = {
    'wifi_on_off' : [ 'on', 'off' ],
    'airplane_mode' : [ 'on', 'off'],
}

####################    
def random_ids(max_nodes_impacted):
    how_many = random.randint(1, max_nodes_impacted)
    return [ random.choice(node_ids) for i in range(how_many)]

# heuristics to avoid too inconsistent data
def normalize_status(node_info):
    # None means do not mention this key at all
    none_keys = { k for k in node_info if node_info[k] is None }
    for k in none_keys:
        del node_info[k]
    # avoid producing too inconsistent data
    if 'control_ssh' in node_info and node_info['control_ssh'] != 'off':
        node_info.update({'cmc_on_off' : 'on',
                          'control_ping' : 'on',
                      })
    return node_info

def random_node_status(id, index=0):
    # for testing incomplete news on the livemap side
    # we expose one or the other or both
    # however the default always expose the full monty
    node_info = { 'id' : id }
    # fill node_info with all known keys
    node_info.update( { field : random.choice(values) 
                       for field, values in nodes_field_possible_values.items() })
    # make sure this is mostly consistent
    normalize_status(node_info)
    # index == 0 means we need a complete record
    # otherwise let's remove some
    items_to_remove = index % len(nodes_field_possible_values)
    keys_to_remove = random.sample(nodes_field_possible_values.keys(), items_to_remove)
    for field in keys_to_remove:
        if field in node_info:
            del node_info[field]
    return node_info

def random_phone_status(id):
    phone_info = { 'id' : id }
    # fill phone_info with all known keys
    phone_info.update( { field : random.choice(values) 
                       for field, values in phones_field_possible_values.items() })
    return phone_info

# too lazy to get this properly (need to turn off server auth)
leases_url = "https://faraday.inria.fr:12346/resources/leases";
leases_file = "LEASES"
nightly = 'inria_r2lab.nightly'
other_slice = 'inria_r2lab.tutorial'

def get_leases():
    print("WARNING: get_leases returns a hard-wired set of leases today")
    today = datetime.datetime.now()
    slices_specs = [
        # slicename - hour-from - hour-until
        (nightly, 8, 10),
        (nightly, 13, 15),
        (nightly, 17, 18),
        (other_slice, 3, 4),
        (other_slice, 20, 21),
    ]
    return [
        {
            "uuid" : id + 100,
            "slicename" : slicename,
            "ok" : True,
            "valid_from" : "{:%Y-%m-%d}T{:02d}:00:00".format(today, start),
            "valid_until" : "{:%Y-%m-%d}T{:02d}:00:00".format(today, end),
        }
        for (id, (slicename, start, end)) in enumerate(slices_specs)
    ]

def main():
    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument('-c', '--cycle', dest='cycle', default=default_cycle,
                        type=float,
                        help="Cycle duration in seconds")
    parser.add_argument('-r', '--runs', dest='runs', default=default_runs,
                        type=int,
                        help="How many runs - means forever")
    parser.add_argument('-n', '--nodes', dest='max_nodes_impacted',
                        default=default_max_nodes_impacted, type=int,
                        help="Maximum number of nodes impacted by each cycle")
    parser.add_argument('-l', '--live', dest='live', action='store_true', default=False,
                        help="If set, only rx/tx data are animated")
    parser.add_argument('-p', '--phone-cycle', default=5, type=int,
                        help='send a random phone status every n cycles')
    parser.add_argument("-u", "--sidecar-url", dest="sidecar_url",
                        default=default_sidecar_url,
                        help="url for the sidecar server")
    parser.add_argument('-v', '--verbose', action='store_true', default=False)
    args = parser.parse_args()

    cycle = args.cycle

    if args.live:
        to_remove = [ k for k in field_possible_values if 'rx' not in k and 'tx' not in k]
        for k in to_remove:
            del field_possible_values[k]

    if args.verbose:
        print("Using cycle {}s".format(cycle))

    url = args.sidecar_url
    print("Connecting to sidecar at {}".format(url))
    socketio = connect_url(url)

    counter = 0
    while True:
        news_infos = [ random_node_status(id, index)
                       for index, id in enumerate(random_ids(args.max_nodes_impacted)) ]
        if args.verbose:
            print("{} -- on {} nodes (id, len(fields)) : {}"
                  .format(counter, len(news_infos),
                          [ (info['id'], len(info)-1) for info in news_infos]))
            print(news_infos[0])
        socketio.emit('info:nodes', json.dumps(news_infos), None)

        # only one phone
        if counter % args.phone_cycle == 0:
            phone_infos = [ random_phone_status(id) for id in [1]]
            if args.verbose:
                print("phone: emitting {}".format(phone_infos[0]))
            socketio.emit('info:phones', json.dumps(phone_infos), None)

        leases = get_leases()
        if leases:
            socketio.emit('info:leases', json.dumps(leases), None)
        counter += 1
        if args.runs and counter >= args.runs:
            break
        time.sleep(cycle)

        
    # xxx should probably clean up the socket io client
    pass

if __name__ == '__main__':
    main()
