import telepot
import shelve
import json
import time
import os
import sys
import subprocess
import http.client
import json2html
import datetime

from json2html import *
from telepot.namedtuple import InlineKeyboardMarkup, InlineKeyboardButton
from telepot.delegate import per_chat_id_in, create_open, pave_event_space, include_callback_query_chat_id
from pprint import pprint

APPNAME = "mvv_bot"
APPVERSION = "1.0.0"


def get_mvg_auth_key() :
    global mvg_auth_key
    return mvg_auth_key

def get_stations_close_to(location) :
    global verbose
    latitude = location.get('latitude')
    longitude = location.get('longitude')

    conn = http.client.HTTPSConnection("www.mvg.de")

    headers = {
        'x-mvg-authorization-key': get_mvg_auth_key(),
        'cache-control': "no-cache",
        }

    conn.request("GET", '/fahrinfo/api/location/nearby?latitude={}&longitude={}'.format(latitude,longitude), headers=headers)

    res = conn.getresponse()
    result = json.loads(res.read().decode("utf-8"))

    # order by distance desc
    try : 
        locations = result.get('locations')
        if len(locations) > 3:
            return locations[0:3]
        else :
            return locations
    except ValueError as e:
        return ""

def getNameFromLocation(x) : 
    try:
        return x.get("name")
    except ValueError:
        return ""

def projectDeparture(departure):
    departure.pop("departureId", None)
    departure.pop("lineBackgroundColor", None)
    if not departure.get("sev"):
        departure.pop("sev", None)
    
    return departure


def get_Departures_From_Location(location_id) :
    global verbose
     
    conn = http.client.HTTPSConnection("www.mvg.de")

    headers = {
        'x-mvg-authorization-key': get_mvg_auth_key(),
        'cache-control': "no-cache",
        }

    conn.request("GET", '/fahrinfo/api/departure/{}'.format(location_id), headers=headers)

    res = conn.getresponse()
    result = json.loads(res.read().decode("utf-8"))
    
    if verbose:
        print(result)

    return list(map(projectDeparture, result.get("departures")))


  
def parseDepartures(departures) :
    result = "**Abfahrt**  **Linie**  **Ziel**\n" 
    for departure in departures :
        depTime = time.strftime("%m. %b. %H:%M:%S" , time.localtime(departure.get("departureTime")/1e3))
        result += '{}  |  {}    {} \n'.format(depTime, departure.get("product").capitalize()+departure.get("label") ,departure.get("destination"))

    return result

class easydict(dict):
    def __missing__(self, key):
        self[key] = easydict()
        return self[key]

class ChatUser(telepot.helper.ChatHandler):

    IdleMessages = ['tüdelü …', '*gähn*', 'Mir ist langweilig.', 'Chill dein Life! Alles cool hier.',
                    'Nix los hier …',  'Hallo-o!!!', 'Alles cool, Digga.', 
                    'Mach du dein Ding. Ich mach hier meins.', 'Alles voll secure in da house.']

    def __init__(self, *args, **kwargs):
        global verbose
        super(ChatUser, self).__init__(*args, **kwargs)
        self.timeout_secs = kwargs.get('timeout')
        self.verbose = verbose

    def open(self, initial_msg, seed):
        content_type, chat_type, chat_id = telepot.glance(initial_msg)
      
    def on_idle(self, event):
        global alerting_on
        if alerting_on:
            ridx = random.randint(0, len(ChatUser.IdleMessages) - 1)
            self.sender.sendMessage(
                ChatUser.IdleMessages[ridx], parse_mode='Markdown')

    def on_close(self, msg):
        if self.verbose:
            print('on_close() called. {}'.format(msg))
        return True

    def send_main_menu(self):
        global alerting_on
        kbd = [
            InlineKeyboardButton(text='Abfahrten', callback_data='dep')
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=[kbd])
        self.sender.sendMessage('Wähle eine Aktion:', reply_markup=keyboard)

    def on_chat_message(self, msg):
        global settings, alerting_on, home_location
        content_type, chat_type, chat_id = telepot.glance(msg)
        if content_type == 'text':
            if self.verbose:
                pprint(msg)
            msg_text = msg['text']
            if msg_text.startswith('/start'):
                self.sender.sendMessage('*Hallo, ich bin dein Heimüberwachungs-Bot!* [' + APPVERSION + ']' +
                                        chr(0x1F916) + "\n\n"
                                        'Ich benachrichtige dich, wenn deine Webcams Bewegungen '
                                        'und laute Geräusche erkannt haben '
                                        'und sende dir ein Video von dem Vorfall.' + "\n",
                                        parse_mode='Markdown')
                self.send_main_menu()
            elif msg_text.startswith('/dep'):
                self.getDepartures(home_location)
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
            self.getDepartures(location)

        else :
            self.sender.sendMessage(
                'Dein "{}" ist im Nirwana gelandet ...'.format(content_type))


    def getDepartures(self, location) :
        global verbose
        if verbose:
            print("Calculating departures")
            self.sender.sendMessage('Suche Haltestellen in der Naehe von:\nLon:\t {}\nLat:\t {}'.format(location.get('longitude'), location.get('latitude')))
        station_list = get_stations_close_to(location)
        if verbose:
            self.sender.sendMessage('Abfahrten fuer Haltestellen abfragen: {}'.format(
                str(list(map(getNameFromLocation, station_list))).replace("[","").replace("]","").replace("'","")
            ))
        for station in station_list :
            departures = get_Departures_From_Location(station_list[0].get("id"))
            foo = '*' + getNameFromLocation(station) +'* \n\n' + parseDepartures(departures)+ '\n\n\n'
            self.sender.sendMessage(foo , parse_mode='Markdown')

authorized_users = None
bot = None
settings = easydict()



def main():
    global bot, authorized_users, alerting_on, mvg_auth_key, verbose, home_location
    config_filename = 'config.json'
    try:
        with open(config_filename, 'r') as config_file:
            config = json.load(config_file)
    except FileNotFoundError:
        print('Error: config file "{}" not found:'.format(config_filename))
        return
    except ValueError as e:
        print('Error: invalid config fie "{}": {}'.format(config_filename, e))
        return
    telegram_bot_token = config.get('telegram_bot_token')
    if not telegram_bot_token:
        print("Error: config file does not contain a 'telegram_bot_token'")
        return

    authorized_users = config.get('authorized_users')
    if type(authorized_users) is not list or len(authorized_users) <= 0:
        print('Error: config file doesn’t contain an `authorized_users` list')
        return

    mvg_auth_key = config.get('mvg_auth_key')
    if not mvg_auth_key:
        print('Error: config file doesn’t contain an `mvg_auth_key`')
        return

    timeout_secs = config.get('timeout_secs',10*60)
    verbose = config.get('verbose')
    home_location = config.get('home_location')
    # image_folder = config.get('image_folder', '/home/ftp-upload')
    alerting_on = True
    bot = telepot.DelegatorBot(telegram_bot_token, [
        include_callback_query_chat_id(pave_event_space())(per_chat_id_in(authorized_users, types='private'),
                                                           create_open,
                                                           ChatUser,
                                                           timeout=timeout_secs)])

    if verbose:
        print('Monitoring ...')
   
    try:
        bot.message_loop(run_forever='Bot listening ...')
    except KeyboardInterrupt:
        pass
    if verbose:
        print('Exiting ...')
   
if __name__ == '__main__':
    main()
