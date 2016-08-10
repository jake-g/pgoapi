#!/usr/bin/env python

import os
import sys
import json
import argparse

from geopy.geocoders import GoogleV3

from bot import PoGoBot

def get_pos_by_name(location_name):
    geolocator = GoogleV3()
    loc = geolocator.geocode(location_name, timeout=10)
    if not loc:
        return None
    return (loc.latitude, loc.longitude, loc.altitude)

def init_config():
    parser = argparse.ArgumentParser()
    config_file = "config.json"

    # If config file exists, load variables from json
    config = {}
    if os.path.isfile(config_file):
        with open(config_file) as data:
            config.update(json.load(data))
    if "powerquotient" in config:
        config["minpq"] = config["powerquotient"]
        del config["powerquotient"]

    # Read passed in Arguments
    required = lambda x: not x in config
    parser.add_argument("-a", "--auth_service", help="Auth Service ('ptc' or 'google')", required=required("auth_service"))
    parser.add_argument("-u", "--username", help="Username", required=required("username"))
    parser.add_argument("-p", "--password", help="Password")
    parser.add_argument("-l", "--location", help="Location")
    parser.add_argument("-k", "--key", help="Google Maps API Key", required=required("key"))
    parser.add_argument("-c", "--coords", type=str, help="External bounds and location coordinate overide file")
    parser.add_argument("-v", "--revisit", type=float, help="Revisit timeout for TPS algo", required=required("revisit"))
    parser.add_argument("-m", "--minpokemon", type=int, help="Minimum number of pokemon for auto transfing", required=required("minpokemon"))
    parser.add_argument("-s", "--speed", type=float, help="Travel speed in miles per hour", required=required("speed"))
    parser.add_argument("-r", "--radius", type=int, help="S2 Cell search radius", required=required("radius"))
    parser.add_argument("--minpq", type=int, help="Minimum power quotient for keeping pokemon", required=required("minpq"))
    parser.add_argument("--mincp", type=int, help="Minimum combat power for keeping pokemon", required=required("mincp"))
    parser.add_argument("-d", "--debug", help="Debug Mode", action='store_true')
    parser.add_argument("--best_balls_first", action='store_true', help="Prioritize throwing better balls")
    parser.add_argument("--nospin", action='store_true', help="Disable spinning forts")
    parser.add_argument("--nocatch",action='store_true', help="Disable catching pokemon")
    parser.set_defaults(DEBUG=False, nospin=False, nocatch=False, best_balls_first=False)
    args = parser.parse_args()

    if "coords" in args.__dict__ and args.__dict__["coords"] != None:
        if args.__dict__["coords"].endswith(".json"):
            f = args.__dict__["coords"]
        else:
            f = os.path.join(os.path.dirname(os.path.realpath(__file__)), "coords/%s.json" % args.__dict__["coords"])
        with open(f, "r") as coordsf:
            coords = json.load(coordsf)
            clean_coords = {}
            for i in ["bounds","location","snipe"]:
                if i in coords:
                    clean_coords[i] = coords[i]
                elif i in config:
                    del config[i]
            config.update(clean_coords)
        if "snipe" in config and config["snipe"]!=None:
            config["location"] = config["snipe"]

    # Passed in arguments shoud trump
    for key in args.__dict__:
        if args.__dict__[key] != None and key != "coords":
            config[key] = args.__dict__[key]

    if not "location" in config:
        sys.stderr.write("Must provide a location!\n")
        return None

    if config["auth_service"] not in ['ptc', 'google']:
        sys.stderr.write("Invalid Auth service specified! ('ptc' or 'google')\n")
        return None

    return config

if __name__ == '__main__':

    config = init_config()
    if not config:
        sys.exit(1)

    if type(config["location"]) == str:
        config["location"] = get_pos_by_name(config["location"])
        if not config["location"]:
            sys.exit(2)

    bot = PoGoBot(config)
    bot.run()
