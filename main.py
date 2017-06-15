#!/usr/bin/env python
"""Telegram Bot to access the API from the Munich Public Transport Network"""
# -*- coding: utf-8 -*-
import os
import json
import time
import http.client
from pprint import pprint

import telepot
from telepot.namedtuple import InlineKeyboardMarkup, InlineKeyboardButton
from telepot.delegate import per_chat_id_in, per_chat_id, create_open
from telepot.delegate import pave_event_space, include_callback_query_chat_id

APPNAME = "mvv_bot"
APPVERSION = "1.0.0"
MVG_AUTH_KEY = None
AUTHORIZED_USERS = None
BOT = None
TELEGRAM_BOT_TOKEN = None
VERBOSE = False
HOME_LOCATION = None

def get_mvg_auth_key():
    """ returns the MVG api key"""
    global MVG_AUTH_KEY
    return MVG_AUTH_KEY

def get_stations_close_to(location):
    """returns stations close to a given location"""
    global VERBOSE
    latitude = location.get('latitude')
    longitude = location.get('longitude')

    conn = http.client.HTTPSConnection("www.mvg.de")

    headers = {
        'x-mvg-authorization-key': get_mvg_auth_key(),
        'cache-control': "no-cache",
        }

    conn.request("GET", '/fahrinfo/api/location/nearby?latitude={}&longitude={}'
                 .format(latitude, longitude), headers=headers)

    res = conn.getresponse()
    result = json.loads(res.read().decode("utf-8"))

    # order by distance desc
    try:
        locations = result.get('locations')
        if len(locations) > 3:
            return locations[0:3]
        else:
            return locations
    except ValueError:
        return ""

def get_name_from_station(station):
    """returns a string with the name, distance and products in"""
    products = {
        's' : "S", #S-Bahn
        'u' : "U", #U-Bahn
        't' : "T", #Tram
        'b' : ""
    }

    res = ''

    for product in station.get("products"):
        if product in products:
            res = res + products.get(product)
    try:
        return station.get("name") + ' {} ({}m)'.format(res, station.get("distance"))
    except ValueError:
        return ""

def get_lines_from_station(station):
    """ returns a string with all lines at one station"""
    res = ''

    lines_shortcut_map = {
        "tram" : "T",
        "nachttram" : "NT",
        "sbahn" : "S",
        "ubahn" : "U",
        "bus" : "",
        "nachtbus" : "N",
        "otherlines" : "X"
    }

    delimiter = ", "

    for lines in station.get("lines"):
        if lines in lines_shortcut_map:
            for line in station.get("lines").get(lines):
                res = res + lines_shortcut_map.get(lines) + line + delimiter
    return res[0:len(res)-len(delimiter)]

def project_departure(departure):
    """reduces the fields in departure object"""
    departure.pop("departureId", None)
    departure.pop("lineBackgroundColor", None)
    if not departure.get("sev"):
        departure.pop("sev", None)
    return departure


def get_departures_from_station(station_id):
    """ returns the next 10 departures at a given station"""
    global VERBOSE
    conn = http.client.HTTPSConnection("www.mvg.de")

    headers = {
        'x-mvg-authorization-key': get_mvg_auth_key(),
        'cache-control': "no-cache",
        }

    conn.request("GET", '/fahrinfo/api/departure/{}'.format(station_id), headers=headers)

    res = conn.getresponse()
    result = json.loads(res.read().decode("utf-8"))

    if VERBOSE:
        print(result)

    departures = result.get("departures")

    if len(departures) > 10:
        departures = departures[0:10]

    return list(map(project_departure, departures))


def parse_departures(departures):
    """returns departures in a table-like  string"""
    result = "**Abfahrt**  **Linie**  **Ziel**\n"
    for departure in departures:
        dep_time = time.strftime("%H:%M", time.localtime(departure.get("departureTime")/1e3))
        result += '{}  {}   {}\n'.format(
            dep_time, departure.get("product").capitalize()+
            departure.get("label"), departure.get("destination"))

    return result
"""
class Easydict(dict):
    
    def __missing__(self, key):
        self[key] = Easydict()
        return self[key]
"""
class ChatUser(telepot.helper.ChatHandler):
    """ models a chat user """
    IdleMessages = ['tüdelü …', 'Mir ist langweilig.', 'Chill dein Life! Alles cool hier.',
                    'Nix los hier …', 'Hallo-o!!!', 'Alles cool, Digga.',
                    'Mach du dein Ding. Ich mach hier meins.', 'Alles voll secure in da house.']

    def __init__(self, *args, **kwargs):
        global VERBOSE
        super(ChatUser, self).__init__(*args, **kwargs)
        self.timeout_secs = kwargs.get('timeout')
        self.verbose = VERBOSE

    def open(self, initial_msg, seed):
        """ handle open event"""
        print(str(seed))
        telepot.glance(initial_msg)

    def on_close(self, msg):
        """ handle close event """
        if self.verbose:
            print('on_close() called. {}'.format(msg))
        return True

    def send_main_menu(self):
        """ send main menu to user """
        kbd = [
            InlineKeyboardButton(text='Abfahrten', callback_data='dep')
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=[kbd])
        self.sender.sendMessage('Wähle eine Aktion:', reply_markup=keyboard)

    def on_chat_message(self, msg):
        """ processes a chat message"""
        global HOME_LOCATION
        content_type, chat_type, chat_id = telepot.glance(msg)
        if content_type == 'text':
            if self.verbose:
                pprint(msg)
            msg_text = msg['text']
            if msg_text.startswith('/start'):
                self.sender.sendMessage('*Hallo, ich bin der MVV Bot* [' + APPVERSION + ']' +
                                        chr(0x1F916) + "\n\n"
                                        'Ich benachrichtige dich, wenn deine Webcams Bewegungen '
                                        'und laute Geräusche erkannt haben '
                                        'und sende dir ein Video von dem Vorfall.' + "\n",
                                        parse_mode='Markdown')
                self.send_main_menu()
            elif msg_text.startswith('/dep'):
                self.get_departures(HOME_LOCATION)
            elif msg_text.startswith('/help'):
                self.sender.sendMessage("Verfügbare Kommandos:\n\n"
                                        "/help diese Nachricht anzeigen\n"
                                        "/start den Bot (neu)starten\n"
                                        "/dep Abfahrt von Location neu berechnen\n",
                                        parse_mode='Markdown')
            elif msg_text.startswith('/'):
                self.sender.sendMessage(
                    'Unbekanntes Kommando. /help für weitere Infos eintippen.')
            else:
                self.sender.sendMessage(
                    'Ich bin nicht sehr gesprächig. Tippe /help für weitere Infos ein.')

        elif content_type == 'location':
            if self.verbose:
                pprint(msg)
            location = msg.get('location')
            self.get_departures(location)

        else:
            self.sender.sendMessage(
                'Dein "{}" ist im Nirwana gelandet ...'.format(content_type))


    def get_departures(self, location):
        """sends the departures close to a given location to the user"""
        global VERBOSE
        if VERBOSE:
            print("Calculating departures")
            self.sender.sendMessage(
                'Suche Haltestellen in der Nähe von:\nLon:\t {}\nLat:\t {}'
                .format(location.get('longitude'), location.get('latitude')))
        station_list = get_stations_close_to(location)
        if VERBOSE:
            self.sender.sendMessage('Abfahrten fuer Haltestellen abfragen: {}'.format(
                str(list(map(get_name_from_station, station_list)))
                .replace("[", "")
                .replace("]", "")
                .replace("'", "")
            ))
        for station in station_list:
            departures = get_departures_from_station(station_list[0].get("id"))
            message = '*' + get_name_from_station(station) + '*\n' + get_lines_from_station(station) + '\n\n' + parse_departures(departures)+ '\n\n\n'
            self.sender.sendMessage(message, parse_mode='Markdown')

def main():
    """ runs the bot """
    global BOT, AUTHORIZED_USERS, MVG_AUTH_KEY, VERBOSE, HOME_LOCATION, TELEGRAM_BOT_TOKEN
    try:
        config_filename = "config/config.json"
        with open(config_filename, 'r') as config_file:
            config = json.load(config_file)
    except FileNotFoundError:
        print('Error: config file "{}" not found:'.format(config_filename))
        return
    except ValueError as error:
        print('Error: invalid config fie "{}": {}'.format(config_filename, error))
        return

    TELEGRAM_BOT_TOKEN = str(os.environ['TELEGRAM_BOT_TOKEN'])
    if not TELEGRAM_BOT_TOKEN:
        print("Error: config file does not contain a 'telegram_bot_token'")
        return

    AUTHORIZED_USERS = config.get('authorized_users')
    if not isinstance(AUTHORIZED_USERS, list) or len(AUTHORIZED_USERS) <= 0:
        print('Error: config file doesn’t contain an `authorized_users` list')
        return

    MVG_AUTH_KEY = str(os.environ['MVG_AUTH_KEY'])
    if not MVG_AUTH_KEY:
        print('Error: config file doesn’t contain an `mvg_auth_key`')
        return

    timeout_secs = config.get('timeout_secs', 10*60)
    VERBOSE = str(os.environ['VERBOSE']) == 'true'
    HOME_LOCATION = config.get('home_location')
    # image_folder = config.get('image_folder', '/home/ftp-upload')

    BOT = telepot.DelegatorBot(TELEGRAM_BOT_TOKEN, [
        include_callback_query_chat_id(pave_event_space())(
            per_chat_id(types='private'),
            create_open,
            ChatUser,
            timeout=timeout_secs)])

    if VERBOSE:
        print('Monitoring ...')
    try:
        BOT.message_loop(run_forever='Bot listening ...')
    except KeyboardInterrupt:
        pass
    if VERBOSE:
        print('Exiting ...')
if __name__ == '__main__':
    main()
