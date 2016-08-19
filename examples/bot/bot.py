from __future__ import print_function

import os
import sys
import time
import json
import math as pymath
import random
import operator
import numpy as np

import re
abconly = re.compile('[^a-zA-Z]')

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "../.."))
from pgoapi import pgoapi
import pgoapi.exceptions

from s2sphere import LatLng, Angle, Cap, RegionCoverer, math

from gmap import Map
from tsp import mk_matrix, nearest_neighbor, length, localsearch, multistart_localsearch

try:
    xrange
except NameError:
    xrange = range

def get_angle(p1, p2):
    y1, x1 = p1
    y2, x2 = p2
    return pymath.degrees(pymath.atan2(y2-y1, x2-x1))

def get_distance(p1, p2):
    y1, x1 = p1
    y2, x2 = p2
    distance = pymath.sqrt(((x2-x1)**2)+((y2-y1)**2))
    return distance

def get_key_from_pokemon(pokemon):
    return '{}-{}'.format(pokemon['spawn_point_id'], pokemon['encounter_id'])

def angle_between_points(p1, p2):
    lat1, lng1 = p1
    lat2, lng2 = p2
    xDiff = lng2 - lng1
    yDiff = lat2 - lat1
    return pymath.degrees(pymath.atan2(yDiff, xDiff))

def point_in_poly(x, y, poly):
    if (x,y) in poly: return True
    for i in range(len(poly)):
        p1 = None
        p2 = None
        if i==0:
            p1 = poly[0]
            p2 = poly[1]
        else:
            p1 = poly[i-1]
            p2 = poly[i]
        if p1[1] == p2[1] and p1[1] == y and x > min(p1[0], p2[0]) and x < max(p1[0], p2[0]):
            return True
    n = len(poly)
    inside = False
    p1x,p1y = poly[0]
    for i in range(n+1):
        p2x,p2y = poly[i % n]
        if y > min(p1y,p2y):
            if y <= max(p1y,p2y):
                if x <= max(p1x,p2x):
                    if p1y != p2y:
                        xints = (y-p1y)*(p2x-p1x)/(p2y-p1y)+p1x
                    if p1x == p2x or x <= xints:
                        inside = not inside
        p1x,p1y = p2x,p2y
    if inside: return True
    else: return False

class PoGoBot(object):

    def __init__(self, config):
        self.config = config
        self.api = pgoapi.PGoApi()
        self.api.set_position(*self.config["location"])
        self.api.set_authentication(provider=self.config["auth_service"],
                                    username=self.config["username"],
                                    password=self.config["password"])
        self.api._signature_info = {
            "DeviceInfo": {
                "device_brand": self.config["device_brand"] if "device_brand" in self.config else "",
                "device_model": self.config["device_model"] if "device_model" in self.config else "",
                "hardware_manufacturer": self.config["hardware_manufacturer"] if "hardware_manufacturer" in self.config else "",
                "hardware_model": self.config["hardware_model"] if "hardware_model" in self.config else "",
                "firmware_brand": self.config["firmware_brand"] if "firmware_brand" in self.config else ""
            }
        }
        self.api.activate_signature(os.path.expanduser(self.config["encrypt"]))
        self.angle = random.uniform(0,360)

        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "../data/pokemon.json"), "r") as infile:
            self.pokemon_info = json.load(infile)
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "../data/items.json"), "r") as infile:
            self.item_names = json.load(infile)
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "../data/family_ids.json"), "r") as infile:
            self.family_ids = json.load(infile)
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "../data/evoreq.json"), "r") as infile:
            self.evoreq = json.load(infile)

        self.coords = [{'latitude': self.config["location"][0], 'longitude': self.config["location"][1]}]
        self.catches = []
        self.spins = []
        self.pois = {"pokestops": {}, "gyms": {}, "pokemon": {}, "spawn_points": set()}
        self.target = None
        self.visited = {}
        self.inventory = self.empty_inventory()
        self.scan_stats = {}
        self.cell_timestamps = {}
        self.incense_encounters = {}

        if "snipe" in self.config and self.config["snipe"] != None:
            self.softbanned = True
        else:
            self.softbanned = False

        self.last_move_time = time.time()
        self.change_dir_time = self.last_move_time + random.uniform(60,300)

    def pokemon_id_to_name(self, id):
        return (list(filter(lambda j: int(j['Number']) == id, self.pokemon_info))[0]['Name'])

    def process_player(self, player):
        self.player = player["player_data"]

    def prune_inventory(self, delay):
        print("Pruning inventory...")
        first = True
        if sum(self.inventory["items"].values()) < self.player["max_item_storage"]:
            status = "Below"
            limit = "inventory_limits"
        else:
            status = "At"
            limit = "inventory_minimum"
        for il in self.config[limit]:
            if il in self.inventory["items"] and self.inventory["items"][il] > self.config[limit][il]:
                count = self.inventory["items"][il] - self.config[limit][il]
                ret = self.api.recycle_inventory_item(item_id=int(il), count=count)
                if ret["responses"]['RECYCLE_INVENTORY_ITEM']["result"] == 1:
                    if first:
                        print("  %s max inventory..." % status)
                        print("    Recycled:")
                        first = False
                    print("      %d x %s" % (count, self.item_names[il]))
                else:
                    print(ret)
                time.sleep(delay)

    def empty_inventory(self):
        return {
            "items": {},
            "candies": {},
            "pokemon": {},
            "eggs": {},
            "stats": {},
            "applied": [],
            "incubators": {}
        }

    def process_inventory(self, inventory):
        ni = self.empty_inventory()
        balls = []
        mon = 0
        for item in inventory["inventory_delta"]["inventory_items"]:
            item = item["inventory_item_data"]
            if "item" in item:
                if "count" in item["item"]:
                    if item["item"]["item_id"] in [1,2,3]:
                        balls = balls + [item["item"]["item_id"]] * item["item"]["count"]
                    ni["items"][str(item["item"]["item_id"])] = item["item"]["count"]
            elif "candy" in item:
                if "candy" in item["candy"]:
                    ni["candies"][str(item["candy"]["family_id"])] = item["candy"]["candy"]
            elif "pokemon_data" in item:
                if "is_egg" in item["pokemon_data"] and item["pokemon_data"]["is_egg"]:
                    ni["eggs"][item["pokemon_data"]["id"]] = item["pokemon_data"]
                else:
                    mon += 1
                    fam = str(item["pokemon_data"]["pokemon_id"])
                    if not fam in ni["pokemon"]:
                        ni["pokemon"][fam] = []
                    ni["pokemon"][fam].append(item)
            elif "egg_incubators" in item:
                for incubator in item["egg_incubators"]["egg_incubator"]:
                    ni["incubators"][incubator["id"]] = incubator
            elif "player_stats" in item:
                ni["stats"] = item["player_stats"]
            elif "applied_items" in item:
                for itm in item["applied_items"]["item"]:
                    if (itm["expire_ms"]/1000) > time.time():
                        ni["applied"].append(itm)
            else:
                pass
        self.balls = sorted(balls)
        if self.config["best_balls_first"]:
            self.balls = self.balls[::-1]
        self.inventory = ni

    def get_trainer_info(self, hatched, delay):
        req = self.api.create_request()
        req.get_player()
        req.get_inventory()
        ret = req.call()
        if ret and ret["responses"]:
            self.process_player(ret["responses"]["GET_PLAYER"])
            self.process_inventory(ret["responses"]["GET_INVENTORY"])
        if hatched:
            pokemon, stardust, candy, xp = hatched
            print("  Hatched %d eggs:..." % len(pokemon))
            print("    Pokemon:")
            for p in pokemon:
                found = False
                for _,fam in self.inventory["pokemon"].items():
                    for pp in fam:
                        if pp["pokemon_data"]["id"] == p:
                            print("      %s" % p)
                            found = True
                            break
                    if found:
                        break
            print("    Experience: %d" % sum(xp))
            print("    Stardust: %d" % sum(stardust))
            print("    Candy: %d" % sum(candy))
        he = 0
        if "eggs_hatched" in self.inventory["stats"]:
            self.inventory["stats"]["eggs_hatched"]
        psv = 0
        if "poke_stop_visits" in self.inventory["stats"]:
            self.inventory["stats"]["poke_stop_visits"]
        print("Getting trainer information...")
        print("  Trainer level: %d" % self.inventory["stats"]["level"])
        print("  Experience: %d" % self.inventory["stats"]["experience"])
        print("  Next level experience needed: %d" % (self.inventory["stats"]["next_level_xp"]-self.inventory["stats"]["experience"]))
        print("  Kilometers walked: %.2f" % self.inventory["stats"]["km_walked"])
        print("  Stardust: %d" % [cur["amount"] for cur in self.player["currencies"] if cur["name"] == "STARDUST"][0])
        print("  Hatched eggs: %d" % he)
        print("  Pokestops visited: %d" % psv)
        print("  Unique pokedex entries: %d" % (self.inventory["stats"]["unique_pokedex_entries"]))
        print("  Pokemon storage: %d/%d" % (sum([len(v) for k,v in self.inventory["pokemon"].items()]) + len(self.inventory["eggs"]), self.player["max_pokemon_storage"]))
        print("  Egg storage: %d/%d" % (len(self.inventory["eggs"]), 9))
        first = True
        for _,ib in self.inventory["incubators"].items():
            if 'pokemon_id' in ib:
                if first:
                    print("  Loaded incubators:")
                    first = False
                print("    Remaining km: %.2f" % (ib["target_km_walked"]-self.inventory["stats"]["km_walked"]))
        print("  Item storage: %d/%d" % (sum(self.inventory["items"].values()), self.player["max_item_storage"]))
        first = True
        for i in self.inventory["items"]:
            if first:
                print("  Inventory:")
                first = False
            print("    %d x %s" % (self.inventory["items"][i], self.item_names[str(i)]))
        first = True
        for i in self.inventory["applied"]:
            if first:
                print("  Applied items:")
                first = False
            print("    %s has %.2f minutes left" % (self.item_names[str(i["item_id"])], ((i["expire_ms"]/1000)-time.time())/60))

    def get_hatched_eggs(self, delay):
        pokemon = []
        stardust = 0
        candy = 0
        xp = 0
        print("Getting hatched eggs...")
        ret = self.api.get_hatched_eggs()
        if 'pokemon_id' in ret["responses"]["GET_HATCHED_EGGS"]:
            hatched = (
                ret["responses"]["GET_HATCHED_EGGS"]["pokemon_id"],
                ret["responses"]["GET_HATCHED_EGGS"]["stardust_awarded"],
                ret["responses"]["GET_HATCHED_EGGS"]["candy_awarded"],
                ret["responses"]["GET_HATCHED_EGGS"]["experience_awarded"]
            )
        else:
            hatched = None
        time.sleep(delay)
        return hatched

    def get_rewards(self, delay):
        print("Getting level-up rewards...")
        ret = self.api.level_up_rewards(level=self.inventory["stats"]["level"])
        if ret["responses"]["LEVEL_UP_REWARDS"]["result"] == 1 and "items_awarded" in ret["responses"]["LEVEL_UP_REWARDS"]:
            print("  Items:")
            ni = {}
            for item in ret["responses"]["LEVEL_UP_REWARDS"]["items_awarded"]:
                if not item["item_id"] in ni:
                    ni[item["item_id"]] = 1
                else:
                    ni[item["item_id"]] += 1
            for item in ni:
                print("    %d x %s" % (ni[item], self.item_names[str(item)]))
        time.sleep(delay)

    EARTH_RADIUS = 6371 * 1000
    def get_cell_ids(self, lat, long, radius=500, level=15):
        # Max values allowed by server according to this comment:
        # https://github.com/AeonLucid/POGOProtos/issues/83#issuecomment-235612285
        if radius > 1500:
            radius = 1500  # radius = 1500 is max allowed by the server
        region = Cap.from_axis_angle(LatLng.from_degrees(lat, long).to_point(), Angle.from_degrees(360*radius/(2*math.pi*self.EARTH_RADIUS)))
        coverer = RegionCoverer()
        coverer.min_level = level
        coverer.max_level = level
        print("  Requesting level %d to %d S2 cells..." % (coverer.min_level, coverer.max_level))
        cells = coverer.get_covering(region)
        cells = cells[:100]  # len(cells) = 100 is max allowed by the server
        return sorted([x.id() for x in cells])

    def get_pois(self, delay):
        print("Getting POIs...")
        lat, lng, alt = self.api.get_position()
        level = 15
        if not level in self.scan_stats:
            self.scan_stats[level] = {"wild_pokemon": 0, "spawn_points": 0}
        cell_ids = self.get_cell_ids(lat, lng, level=level, radius=self.config["radius"])
        for cid in cell_ids:
            if not cid in self.cell_timestamps:
                self.cell_timestamps[cid] = 0
        timestamps = [self.cell_timestamps[cid] for cid in cell_ids]
        # for i in xrange(len(timestamps)):
        #     print("    Cell %s, last timestamp: %d" % (cell_ids[i], timestamps[i]))
        ret = self.api.get_map_objects(latitude=lat, longitude=lng, since_timestamp_ms=timestamps, cell_id=cell_ids)
        newpokemon = 0
        newpokestops = 0
        newgyms = 0
        newspawnpoints = 0
        if ret and ret["responses"] and "GET_MAP_OBJECTS" in ret["responses"] and ret["responses"]["GET_MAP_OBJECTS"]["status"] == 1:
            for map_cell in ret["responses"]["GET_MAP_OBJECTS"]["map_cells"]:
                self.cell_timestamps[map_cell["s2_cell_id"]] = map_cell["current_timestamp_ms"]
                if "wild_pokemons" in map_cell:
                    for pokemon in map_cell["wild_pokemons"]:
                        pid = get_key_from_pokemon(pokemon)
                        if not pid in self.pois["pokemon"]:
                            newpokemon += 1
                        pokemon['time_till_hidden_ms'] = time.time() + pokemon['time_till_hidden_ms']/1000
                        self.pois["pokemon"][pid] = pokemon
                if 'forts' in map_cell:
                    for fort in map_cell['forts']:
                        if "bounds" in self.config and not point_in_poly(fort["latitude"], fort["longitude"], self.config["bounds"]):
                            continue
                        if "type" in fort and fort["type"] == 1:
                            if not fort["id"] in self.pois['pokestops']:
                                newpokestops += 1
                            self.pois['pokestops'][fort["id"]] = fort
                        elif not "type" in fort:
                            if not fort["id"] in self.pois['gyms']:
                                newgyms += 1
                            self.pois['gyms'][fort["id"]] = fort
                if 'spawn_points' in map_cell:
                    for sp in map_cell['spawn_points']:
                        if "bounds" in self.config and not point_in_poly(sp["latitude"], sp["longitude"], self.config["bounds"]):
                            continue
                        sp = (sp["latitude"],sp["longitude"])
                        if not sp in self.pois["spawn_points"]:
                            self.pois["spawn_points"].add(sp)
                            newspawnpoints += 1
                if 'nearby_pokemons' in map_cell:
                    pass#print("nearby_pokemons", map_cell['nearby_pokemons'])
                if 'catchable_pokemons' in map_cell:
                    pass#print('catchable_pokemons', map_cell['catchable_pokemons'])
        if newpokemon > 0:
            print("    Found %d new pokemon." % newpokemon)
            self.scan_stats[level]["wild_pokemon"] += newpokemon
        if newpokestops > 0:
            print("    Found %d new pokestops." % newpokestops)
        if newgyms > 0:
            print("    Found %d new gyms." % newgyms)
        if newspawnpoints > 0:
            print("    Found %d new spawnpoints." % newgyms)
            self.scan_stats[level]["spawn_points"] += newspawnpoints
        if len(self.scan_stats.keys()) > 0:
            print("  Scan stats by level:")
            for level, stat in self.scan_stats.items():
                print('    %s {"wild_pokemon": %d, "spawn_points": %d}' % (level, stat["wild_pokemon"], stat["spawn_points"]))
        time.sleep(delay)

    def prune_expired_pokemon(self):
        print("Pruning expired pokemon...")
        expired = []
        for k, pokemon in self.pois["pokemon"].items():
            if pokemon['time_till_hidden_ms'] <= time.time():
                expired.append(k)
        if len(expired) > 0:
            for k in expired:
                del self.pois["pokemon"][k]
            print("  %d pokemon expired." % len(expired))

    def spin_pokestop(self, pokestop, lat, lng, alt, delay, clear=False):
        status = 0
        ret = self.api.fort_search(fort_id=pokestop['id'], fort_latitude=pokestop['latitude'], fort_longitude=pokestop['longitude'], player_latitude=lat, player_longitude=lng)
        if "experience_awarded" in ret["responses"]["FORT_SEARCH"]:
            self.spins.append(pokestop)
            self.visited[pokestop["id"]] = time.time()
            if pokestop["id"] == self.target:
                self.target = None
            if clear:
                print("")
            print("  Spun pokestop and got:")
            xp = ret["responses"]["FORT_SEARCH"]["experience_awarded"]
            print("    Experience: %d" % xp)
            if "items_awarded" in ret["responses"]["FORT_SEARCH"]:
                print("    Items:")
                ni = {}
                for item in ret["responses"]["FORT_SEARCH"]["items_awarded"]:
                    if not item["item_id"] in ni:
                        ni[item["item_id"]] = 1
                    else:
                        ni[item["item_id"]] += 1
                for item in ni:
                    print("      %d x %s" % (ni[item], self.item_names[str(item)]))
            status = 1
        else:
            if ret["responses"]["FORT_SEARCH"]["result"] == 3:
                print(pokestop)
            elif len(ret["responses"]["FORT_SEARCH"].keys()) == 1 and ret["responses"]["FORT_SEARCH"]["result"] == 1:
                status = -1
        return (status, ret["responses"]["FORT_SEARCH"]["result"])

    def unsoftban(self, delay):
        print("Testing softban...")
        lat, lng, alt = self.api.get_position()
        nearest = (None, float("inf"))
        for pid, pokestop in self.pois["pokestops"].items():
            d = get_distance((pokestop['latitude'], pokestop['longitude']), (lat, lng))
            if d < nearest[1]:
                nearest = (pokestop, d)
        if nearest[0] != None:
            self.api.set_position(nearest[0]['latitude'], nearest[0]['longitude'], alt)
            print("  Attempting 40 spin fix.")
            print("    Spin ",end="")
            spins = 40
            for i in xrange(spins):
                print("%d" % (i+1),end="")
                sys.stdout.flush()
                s,r = self.spin_pokestop(nearest[0], lat, lng, alt, delay, True)
                time.sleep(delay)
                if s != -1:
                    self.softbanned = False
                    break
                if i < spins-1:
                    print(",",end="")

    def spin_pokestops(self, delay):
        print("Spinning pokestops...")
        lat, lng, alt = self.api.get_position()
        for pid, pokestop in self.pois["pokestops"].items():
            if get_distance((pokestop['latitude'], pokestop['longitude']), (lat, lng)) < 0.0004435:
                if not pid in self.visited and not "cooldown_complete_timestamp_ms" in pokestop:
                    s,r = self.spin_pokestop(pokestop, lat, lng, alt, delay)
                    time.sleep(delay)
                    if s == -1:
                        print("  Softban detected, attempting 40 spin fix.")
                        print("    Spin ")
                        spins = 40
                        for i in xrange(spins):
                            print("%d" % (i+1))
                            s,r = self.spin_pokestop(pokestop, lat, lng, alt, delay)
                            time.sleep(delay)
                            if s == 1:
                                break
                            if i < spins-1:
                                print(",")
                        print("")

    def clean_encounter(self, kind, upid):
        if kind == "incense" and upid in self.incense_encounters.keys():
            del self.incense_encounters[upid]
        elif kind == "wild" and upid in self.pois["pokemon"].keys():
            del self.pois["pokemon"][upid]

    def catch_pokemon(self, pokemon, kind, balls, delay, upid=None, pcap=None):
        minball = 1
        eid = pokemon["encounter_id"]
        spid = pokemon["spawn_point_id"]
        pid = pokemon["pokemon_data"]["pokemon_id"]
        if pcap and "capture_probability" in pcap:
            pcap = pcap["capture_probability"][0]
            print("    Pokeball capture probability is %.2f..." % pcap)
            if pcap < .25 and "701" in self.inventory["items"]:
                print("      Using a %s..." % self.item_names["701"], end="")
                ret = self.api.use_item_capture(item_id=701, encounter_id=eid, spawn_point_id=spid)
                if "item_capture_mult" in ret["responses"]["USE_ITEM_CAPTURE"]:
                    print("success.")
                    print("        Capture multiplier %.2f..." % ret["responses"]["USE_ITEM_CAPTURE"]["item_capture_mult"])
                    pcap = pcap * ret["responses"]["USE_ITEM_CAPTURE"]["item_capture_mult"]
                    print("        New capture probability is %.2f..." % pcap)
                else:
                    print("failed.")
                    print(ret)
                time.sleep(delay)
            if pcap < .3:
                minball = 2
            elif pcap < .15:
                minball = 3
        clean = None
        while True:
            normalized_reticle_size = 1.950 - random.uniform(0, .15)
            normalized_hit_position = 1.0
            spin_modifier = 1.0 - random.uniform(0, .1)
            if len(balls) == 0:
                break
            if minball in balls:
                ball = balls.pop(balls.index(minball))
            else:
                ball = balls.pop()
            print("    Throwing a %s..." % self.item_names[str(ball)], end="")
            ret = self.api.catch_pokemon(encounter_id=eid, spawn_point_id=spid, pokeball=ball, normalized_reticle_size = normalized_reticle_size, hit_pokemon=True, spin_modifier=spin_modifier, normalized_hit_position=normalized_hit_position)
            if ret["responses"]["CATCH_POKEMON"]["status"] == 1:
                print("success.")
                clean = (kind, upid)
                self.catches.append((kind,pokemon))
                print("      Experience: %d" % sum(ret["responses"]["CATCH_POKEMON"]["capture_award"]["xp"]))
                print("      Stardust: %d" % sum(ret["responses"]["CATCH_POKEMON"]["capture_award"]["stardust"]))
                print("      Candies: %d" % sum(ret["responses"]["CATCH_POKEMON"]["capture_award"]["candy"]))
                break
            elif ret["responses"]["CATCH_POKEMON"]["status"] == 0:
                print("error.")
                break
            elif ret["responses"]["CATCH_POKEMON"]["status"] == 2:
                print("escape.")
                if not self.config["best_balls_first"]:
                    minball += 1
                if minball > 3:
                    minball = 3
                time.sleep(delay)
            elif ret["responses"]["CATCH_POKEMON"]["status"] == 3:
                print("flee.")
                clean = (kind, upid)
                break
            elif ret["responses"]["CATCH_POKEMON"]["status"] == 4:
                print("missed.")
                time.sleep(delay)
        time.sleep(delay)
        return clean

    def catch_wild_pokemon(self, delay):
        print("Looking for wild pokemon encounters...")
        lat, lng, alt = self.api.get_position()
        clean = []
        for pid, pokemon in self.pois["pokemon"].items():
            ret = self.api.encounter(encounter_id=pokemon['encounter_id'],
                                     spawn_point_id=pokemon['spawn_point_id'],
                                     player_latitude = lat,
                                     player_longitude = lng)
            time.sleep(delay)
            if ret["responses"]["ENCOUNTER"]["status"] == 1:
                pokemon = ret["responses"]["ENCOUNTER"]["wild_pokemon"]
                pcap =  ret["responses"]["ENCOUNTER"]['capture_probability']
                print("  Encountered a %d PQ %d CP wild %s at %f,%f..." % (self.calc_pq(pokemon), pokemon['pokemon_data']["cp"], self.pokemon_id_to_name(pokemon["pokemon_data"]["pokemon_id"]), pokemon["latitude"], pokemon["longitude"]))
                clean.append(self.catch_pokemon(pokemon, "wild", self.balls, delay, pid, pcap))
            else:
                print(ret)
        for c in clean:
            if c: self.clean_encounter(*c)


    def catch_lure_pokemon(self, delay):
        print("Lookng for lure pokemon encounters...")
        clean = []
        for fid, fort in self.pois["pokestops"].items():
            if "lure_info" in fort:
                lat, lng, alt = self.api.get_position()
                pokemon = {
                    "encounter_id": fort["lure_info"]["encounter_id"],
                    "spawn_point_id": fort["lure_info"]["fort_id"],
                    "pokemon_data": {"pokemon_id": fort["lure_info"]["active_pokemon_id"]},
                    "latitude": fort["latitude"],
                    "longitude": fort["longitude"]
                }
                pid = get_key_from_pokemon(pokemon)
                if not pid in self.catches:
                    ret = self.api.disk_encounter(encounter_id=pokemon["encounter_id"],
                                                  fort_id=pokemon["spawn_point_id"],
                                                  player_latitude=lat,
                                                  player_longitude=lng)
                    time.sleep(delay)
                    if ret["responses"]["DISK_ENCOUNTER"]["result"] == 1:
                        pokemon = ret["responses"]["DISK_ENCOUNTER"]
                        pokemon['encounter_id'] = fort["lure_info"]["encounter_id"]
                        pokemon["spawn_point_id"] = fort["lure_info"]["fort_id"]
                        pokemon["latitude"] = fort["latitude"]
                        pokemon["longitude"] = fort["longitude"]
                        pcap =  ret["responses"]["DISK_ENCOUNTER"]['capture_probability']
                        print("  Encountered a %d PQ %d CP lured %s at %f,%f..." % (self.calc_pq(pokemon), pokemon['pokemon_data']["cp"], self.pokemon_id_to_name(pokemon["pokemon_data"]["pokemon_id"]), pokemon["latitude"], pokemon["longitude"]))
                        clean.append(self.catch_pokemon(pokemon, "lure", self.balls, delay, pid, pcap))
                    else:
                        print(ret)
        for c in clean:
            if c: self.clean_encounter(*c)

    def catch_incense_pokemon(self, delay):
        print("Lookng for incense encounters...")
        lat, lng, alt = self.api.get_position()
        ret = self.api.get_incense_pokemon(player_latitude=lat,
                                           player_longitude=lng)
        time.sleep(delay)
        clean = []
        if ret["responses"]["GET_INCENSE_POKEMON"]["result"] == 1:
            pokemon = ret["responses"]["GET_INCENSE_POKEMON"]
            pokemon['spawn_point_id'] = pokemon["encounter_location"]
            pokemon['pokemon_data'] = {"pokemon_id": pokemon["pokemon_id"]}
            self.incense_encounters[get_key_from_pokemon(pokemon)] = pokemon
        for pid, pokemon in self.incense_encounters.items():
            ret = self.api.incense_encounter(encounter_id=pokemon["encounter_id"],
                                             encounter_location=pokemon["spawn_point_id"])
            time.sleep(delay)
            if ret["responses"]["INCENSE_ENCOUNTER"]["result"] == 1:
                pcap =  ret["responses"]["INCENSE_ENCOUNTER"]['capture_probability']
                print("  Encountered an %d PQ %d CP incense %s..." % (self.calc_pq(pokemon), pokemon['pokemon_data']["cp"], self.pokemon_id_to_name(pokemon["pokemon_id"])))
                clean.append(self.catch_pokemon(pokemon, "incense", self.balls, delay, pid, pcap))
            else:
                print(ret)
        for c in clean:
            if c: self.clean_encounter(*c)

    def update_path(self):
        print("Updating path...")
        lat, lng, alt = self.api.get_position()
        if self.target == None:
            print("  Picking new target...")
            coord = [(lat, lng)]
            fids = []
            for fid, pokestop in self.pois["pokestops"].items():
                if not pokestop["id"] in self.visited and not "cooldown_complete_timestamp_ms" in pokestop:
                    fids.append(fid)
                    coord.append((pokestop["latitude"], pokestop["longitude"]))
            l = len(fids)
            if l > 0:
                n, D = mk_matrix(coord, get_distance)
                tour = nearest_neighbor(n, 0, D)
                tour.remove(0)
                tour[:] = [t-1 for t in tour]
                lures = []
                for i in xrange(min(len(tour),5)):
                    if 'active_fort_modifier' in self.pois["pokestops"][fids[tour[i]]] and not fids[tour[i]] in self.visited:
                        lures.append(i)
                if len(lures) > 0 and min(lures) > 0:
                    print("    Prioritizing pokestop with lure...")
                    i = min(lures)
                else:
                    while True:
                        i = np.random.poisson(self.config["noise"],1)[0]
                        if i < len(tour):
                            break
                self.target = fids[tour[i]]
        remove = []
        for k,v in self.visited.items():
            if v + self.config["revisit"] <= time.time():
                remove.append(k)
        for k in remove:
            del self.visited[k]

    def move(self, mph=5):
        print("Moving...")
        now = time.time()
        delta = now - self.last_move_time
        lat, lng, alt = self.api.get_position()
        r = 1.0/69.0/60.0/60.0*mph*delta
        if len(self.balls) > 0 and len(self.incense_encounters.keys()) > 0:
            print("  Heading towards nearby incense pokemon...")
            nearest = (None, float("inf"))
            for pid, pokemon in self.incense_encounters.items():
                d = get_distance((pokemon['latitude'], pokemon['longitude']), (lat, lng))
                if d < nearest[1]:
                    nearest = (pokemon, d)
            if nearest[1] < r:
                lat = nearest[0]["latitude"]
                lng = nearest[0]["longitude"]
            else:
                self.angle = get_angle((lat, lng), (nearest[0]["latitude"], nearest[0]["longitude"]))
                lat = lat + pymath.sin(pymath.radians(self.angle)) * r
                lng = lng + pymath.cos(pymath.radians(self.angle)) * r
        elif len(self.balls) > 0 and len(self.pois["pokemon"]) > 0:
            print("  Heading towards nearby wild pokemon...")
            nearest = (None, float("inf"))
            for pid, pokemon in self.pois["pokemon"].items():
                d = get_distance((pokemon['latitude'], pokemon['longitude']), (lat, lng))
                if d < nearest[1]:
                    nearest = (pokemon, d)
            if nearest[1] < r:
                lat = nearest[0]["latitude"]
                lng = nearest[0]["longitude"]
            else:
                self.angle = get_angle((lat, lng), (nearest[0]["latitude"], nearest[0]["longitude"]))
                lat = lat + pymath.sin(pymath.radians(self.angle)) * r
                lng = lng + pymath.cos(pymath.radians(self.angle)) * r
        else:
            print("  Heading to a pokestop...")
            target = None
            if self.target:
                target = self.pois["pokestops"][self.target]
                self.angle = get_angle((lat, lng), (target["latitude"], target["longitude"]))
            else:
                self.angle = random.uniform(0,360)
            if target and get_distance((lng, lat), (target["longitude"], target["latitude"])) < r:
                lat = target["latitude"]
                lng = target["longitude"]
                print("    Visited a pokestop...")
                self.visited[self.target] = time.time()
                self.target = None
            else:
                lat = lat + pymath.sin(pymath.radians(self.angle)) * r
                lng = lng + pymath.cos(pymath.radians(self.angle)) * r
        self.api.set_position(lat, lng, alt)
        self.coords.append({'latitude': lat, 'longitude': lng})
        self.last_move_time = now

    def save_map(self):
        print("Saving map...")
        lat, lng, alt = self.api.get_position()
        map = Map()
        map._player = [lat, lng]
        if "bounds" in self.config:
            for bound in self.config["bounds"]:
                map.add_bound(bound)
        for coord in self.coords:
            map.add_position((coord['latitude'], coord['longitude']))
        for _,catch in self.catches:
            pid = catch["pokemon_data"]["pokemon_id"]
            lat = catch["latitude"]
            lng = catch["longitude"]
            map.add_point2((lat, lng), "%03d" % pid)
        if "snipe" in self.config and self.config["snipe"] != None:
            map.add_point1((self.config["snipe"][0], self.config["snipe"][1]), "http://maps.google.com/mapfiles/ms/icons/red.png")
        for spin in self.spins:
            map.add_point1((spin['latitude'], spin['longitude']), "http://maps.google.com/mapfiles/ms/icons/blue.png")
        for sp in self.pois["spawn_points"]:
            map.add_point1(sp, "http://www.andrew.cmu.edu/user/rhope/darkgray-dot-4x4.png")
        for _, pokestop in self.pois["pokestops"].items():
            if pokestop["id"] in self.visited:
                map.add_point1((pokestop['latitude'], pokestop['longitude']), "http://www.srh.noaa.gov/images/tsa/timeline/gray-circle.png")
            else:
                if 'active_fort_modifier' in pokestop:
                    map.add_point1((pokestop['latitude'], pokestop['longitude']), "http://www.srh.noaa.gov/images/tsa/timeline/red-circle.png")
                else:
                    map.add_point1((pokestop['latitude'], pokestop['longitude']), "http://www.srh.noaa.gov/images/tsa/timeline/green-circle.png")
        for _, gym in self.pois["gyms"].items():
            map.add_point1((gym['latitude'], gym['longitude']), "http://www.srh.noaa.gov/images/tsa/timeline/blue-circle.png")
        # for _, pokemon in self.pois["pokemon"].items():
        #     map.add_point((pokemon['latitude'], pokemon['longitude']), "http://www.srh.noaa.gov/images/tsa/timeline/red-circle.png")
        # for _, sp in self.spawnpoints.items():
        #     map.add_point((sp['latitude'], sp['longitude']), "http://www.srh.noaa.gov/images/tsa/timeline/gray-circle.png")
        if self.target:
            target = self.pois["pokestops"][self.target]
            map.add_point1((target['latitude'], target['longitude']), "http://maps.google.com/mapfiles/ms/icons/green.png")

        with open("maptrace.html", "w") as out:
            print(map, file=out)

    def save_config(self):
        print("Saving config...")
        self.config["location"] = self.api.get_position()
        dump = {}
        dump.update(self.config)
        if "snipe" in dump:
            del dump["snipe"]
        with open("config.json", "w") as out:
            json.dump(dump, out, indent=2, sort_keys=True)

    def load_incubators(self):
        print("Loading incubators...")
        for _,ib in self.inventory["incubators"].items():
            if not 'pokemon_id' in ib:
                if len(self.inventory["eggs"]) > 0:
                    bestegg = (None, 0)
                    for eid, egg in self.inventory["eggs"].items():
                        if egg["egg_km_walked_target"] > bestegg[1]:
                            good = True
                            for _,ib2 in self.inventory["incubators"].items():
                                if "pokemon_id" in ib2 and eid == ib2["pokemon_id"]:
                                    good = False
                                    break
                            if good:
                                bestegg = (egg, egg["egg_km_walked_target"])
                    ret = self.api.use_item_egg_incubator(item_id=ib['id'], pokemon_id=bestegg[0]['id'])
                    if ret["responses"]['USE_ITEM_EGG_INCUBATOR']["result"] == 1:
                        print("  A %fkm egg was loaded." % bestegg[1])
                        del self.inventory["eggs"][eid]
                    else:
                        print(ret)


    def calc_pq(self, pokemon):
        pq = 0
        for iv in ["individual_attack", "individual_defense", "individual_stamina"]:
            if iv in pokemon["pokemon_data"]:
                pq += pokemon["pokemon_data"][iv]
        return int(round(pq/45.0,2)*100)

    def circle_poly(x,y,r):
        for i in range(100):
            ang = i/100 * pymath.pi * 2
            yield (x + r * pymath.cos(ang), y + r * pymath.sin(ang))

    def process_candies(self):
        print("Processing candies...")
        self.enabled_evolutions = {}
        if len(self.inventory["candies"].keys()) > 0:
            candies = {}
            candies.update(self.inventory["candies"])
            for pid, req in sorted(self.evoreq.items(), key=operator.itemgetter(1), reverse=True):
                fid = str(self.family_ids[pid])
                if fid in candies.keys():
                    evos, extra = divmod(candies[fid], req)
                    if evos > 0:
                        self.enabled_evolutions[pid] = evos
                        candies[fid] -= evos
            if len(self.enabled_evolutions.keys()) > 0:
                print("  Candy cost met for evolutions:")
                for pid, req in sorted(self.evoreq.items(), key=operator.itemgetter(1), reverse=True):
                    if pid in self.enabled_evolutions.keys():
                        evos = self.enabled_evolutions[pid]
                        extra = ""
                        isize = 0
                        if pid in self.inventory["pokemon"]:
                            isize = len(self.inventory["pokemon"][pid])
                            if isize < evos:
                                extra = " (%d more pokemon needed)" % (evos-isize)
                        else:
                            extra = " (%d more pokemon needed)" % evos
                        print("    %d x %s%s" % (evos, self.pokemon_id_to_name(int(pid)), extra))

    def transfer_pokemon(self, delay):
        t = 0
        if (sum([len(v) for k,v in self.inventory["pokemon"].items()]) + len(self.inventory["eggs"])) > self.config["minpokemon"]:
            print("Transfering pokemon...")
            transferable_pokemon = []
            for pid in self.inventory["pokemon"]:
                if "whitelist" in self.config and str(pid) in map(str,self.config["whitelist"]):
                    continue
                if pid in self.evoreq.keys():
                    if pid not in self.enabled_evolutions:
                        for pokemon in self.inventory["pokemon"][pid]:
                            pq = self.calc_pq(pokemon)
                            if pq < self.config["minpq"] and pokemon["pokemon_data"]["cp"] < self.config["mincp"]:
                                transferable_pokemon.append((pokemon, pq))
                    else:
                        isize = len(self.inventory["pokemon"][pid])
                        if isize > self.enabled_evolutions[pid]:
                            count = isize - self.enabled_evolutions[pid]
                            for pokemon in self.inventory["pokemon"][pid]:
                                pq = self.calc_pq(pokemon)
                                if pq < self.config["minpq"] and pokemon["pokemon_data"]["cp"] < self.config["mincp"]:
                                    transferable_pokemon.append((pokemon, pq))
                                    count -= 1
                                if count == 0:
                                    break
                else:
                    for pokemon in self.inventory["pokemon"][pid]:
                        pq = self.calc_pq(pokemon)
                        if pq < self.config["minpq"] and pokemon["pokemon_data"]["cp"] < self.config["mincp"]:
                            transferable_pokemon.append((pokemon, pq))
            for pokemon, pq in transferable_pokemon:
                ret = self.api.release_pokemon(pokemon_id=pokemon["pokemon_data"]["id"])
                if ret and "RELEASE_POKEMON" in ret['responses'] and ret["responses"]["RELEASE_POKEMON"]["result"] == 1:
                    print("  A %d PQ %d CP %s was released." % (pq, pokemon["pokemon_data"]["cp"], self.pokemon_id_to_name(pokemon["pokemon_data"]["pokemon_id"])))
                    t += 1
                time.sleep(delay)
        return t

    def evolve_pokemon(self, delay):
        e = 0
        evolveable_pokemon = []
        lowcost = []
        if len(self.inventory["eggs"]) + sum([len(self.inventory["pokemon"][p]) for p in self.inventory["pokemon"]]) == self.player["max_pokemon_storage"]:
            print("Evolving pokemon...")
            for pid, evos in self.enabled_evolutions.items():
                if pid in self.inventory["pokemon"] and self.evoreq[pid] <= 25:
                    while evos > 0 and len(self.inventory["pokemon"][pid]) > 0:
                        lowcost.append(self.inventory["pokemon"][pid].pop())
                        evos -= 1
                else:
                    if pid in self.inventory["pokemon"]:
                        for pokemon in self.inventory["pokemon"][pid]:
                            if "whitelist" in self.config and str(pid) in map(str,self.config["whitelist"]):
                                if self.calc_pq(pokemon) > self.config["minpq"]:
                                    evolveable_pokemon.append(pokemon)
                            else:
                                evolveable_pokemon.append(pokemon)
            print("  Found %d low cost pokemon evolutions..." % len(lowcost))
            evolveable_pokemon = evolveable_pokemon + lowcost
            print("  There are %d total evolveable pokemon..." % len(evolveable_pokemon))
            if len(evolveable_pokemon) > 100 and "301" in self.inventory["items"]:
                print("  Using a lucky egg...")
                ret = self.api.use_item_xp_boost(item_id=301)
                if ret["responses"]["USE_ITEM_XP_BOOST"]["result"] == 1:
                    print("success.")
                else:
                    print("failed.")
                time.sleep(delay)
            for pokemon in evolveable_pokemon:
                ret = self.api.evolve_pokemon(pokemon_id=pokemon["pokemon_data"]["id"])
                if ret["responses"]["EVOLVE_POKEMON"]["result"] == 1:
                    print("    A %s was evolved." % (self.pokemon_id_to_name(self.family_ids[str(pokemon["pokemon_data"]["pokemon_id"])])))
                    print("      Experience: %d" % ret["responses"]["EVOLVE_POKEMON"]["experience_awarded"])
                    e += 1
                time.sleep(delay)
        return e

    def kill_time(self, delay):
        print("Killing time...")
        time.sleep(delay)

    def play(self):
        delay = .5
        last_map = 0
        self.api.get_player()
        time.sleep(delay)
        throttlesleep = 10
        lastthrottle = None
        self.save_map()
        while True:
            try:
                if self.softbanned:
                    self.get_trainer_info(None, delay)
                if not self.softbanned:
                    self.save_config()
                    hatched = self.get_hatched_eggs(delay)
                    self.get_trainer_info(hatched, delay)
                    self.get_rewards(delay)
                    self.kill_time(delay)
                if last_map + 10 < time.time():
                    self.get_pois(delay)
                    last_map = time.time()
                    self.kill_time(delay)
                if self.softbanned:
                    self.unsoftban(.025)
                if not self.softbanned:
                    self.prune_expired_pokemon()
                    if not self.config["nocatch"] and len(self.balls) > 0:
                        self.catch_wild_pokemon(delay)
                        self.catch_incense_pokemon(delay)
                        self.catch_lure_pokemon(delay)
                    if not self.config["nospin"]:
                        self.spin_pokestops(1)
                    self.load_incubators()
                    self.process_candies()
                    if self.evolve_pokemon(delay):
                        self.last_move_time = time.time()
                        continue
                    if self.config["minpokemon"] >= 0:
                        if self.transfer_pokemon(delay):
                            self.last_move_time = time.time()
                            continue
                    self.prune_inventory(delay)
                    self.update_path()
                    self.move(self.config["speed"])
                self.save_map()
            except pgoapi.exceptions.ServerSideRequestThrottlingException as e:
                if lastthrottle != None and time.time()-lastthrottle < throttlesleep:
                    throttlesleep += 1
                print("Throttling exeption, taking a %d second timeout!" % throttlesleep)
                time.sleep(throttlesleep)
                lastthrottle = time.time()


    def run(self):
        self.play()