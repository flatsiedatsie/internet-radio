"""Internet radio adapter for Candle Controller / WebThings Gateway."""

# test commands to play radio: 
# ffplay -nodisp -vn -infbuf -autoexit http://direct.fipradio.fr/live/fip-midfi.mp3 -volume 100
# SDL_AUDIODRIVER=alsa UDIODEV=bluealsa:DEV=00:00:00:00:00:00 ffplay -nodisp -vn -infbuf -autoexit http://direct.fipradio.fr/live/fip-midfi.mp3 -volume 100

# omxplayer -o local --vol -2000 -z --audio_queue 10 --audio_fifo 10 --threshold 5 http://direct.fipradio.fr/live/fip-midfi.mp3
# omxplayer -o alsa:bluealsa http://direct.fipradio.fr/live/fip-midfi.mp3 --vol -2000 -z --audio_queue 10 --audio_fifo 10 --threshold 5
# omxplayer -o alsa:sysdefault http://direct.fipradio.fr/live/fip-midfi.mp3 --vol -2000 -z --audio_queue 10 --audio_fifo 10 --threshold 5

# omxplayer -o both http://direct.fipradio.fr/live/fip-midfi.mp3 --vol -2000 -z --audio_queue 10 --audio_fifo 10 --threshold 5

# LD_LIBRARY_PATH=/opt/vc/lib omxplayer -o alsa:sysdefault http://live.dancemusic.ro:7000/stream --vol -2000 -z --audio_queue 10 --audio_fifo 10 --threshold 5



import os
import re
import sys

import vlc

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib'))

import json
import math
import time
import datetime
import requests  # noqa
import threading
import subprocess

from gateway_addon import Database, Adapter, Device, Property

try:
    #from gateway_addon import APIHandler, APIResponse
    from .internet_radio_api_handler import * #InternetRadioAPIHandler
    #print("VocoAPIHandler imported")
except Exception as ex:
    print("Unable to load APIHandler (which is used for UI extention): " + str(ex))

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib'))

_TIMEOUT = 3

_CONFIG_PATHS = [
    os.path.join(os.path.expanduser('~'), '.webthings', 'config'),
]

if 'WEBTHINGS_HOME' in os.environ:
    _CONFIG_PATHS.insert(0, os.path.join(os.environ['WEBTHINGS_HOME'], 'config'))



class InternetRadioAdapter(Adapter):
    """Adapter for Internet Radio"""

    def __init__(self, verbose=False):
        """
        Initialize the object.

        verbose -- whether or not to enable verbose logging
        """

        #print("initialising adapter from class")
        self.pairing = False
        self.ready = False
        self.addon_name = 'internet-radio'
        self.DEBUG = False
        self.name = self.__class__.__name__
        Adapter.__init__(self, self.addon_name, self.addon_name, verbose=verbose)



        # Setup persistence
        #for path in _CONFIG_PATHS:
        #    if os.path.isdir(path):
        #        self.persistence_file_path = os.path.join(
        #            path,
        #            'internet-radio-persistence.json'
        #        )
        #        print("self.persistence_file_path is now: " + str(self.persistence_file_path))

        self.addon_path = os.path.join(self.user_profile['addonsDir'], self.addon_name)
        #self.persistence_file_path = os.path.join(os.path.expanduser('~'), '.mozilla-iot', 'data', self.addon_name,'persistence.json')
        self.persistence_file_path = os.path.join(self.user_profile['dataDir'], self.addon_name, 'persistence.json')
        self.bluetooth_persistence_file_path = os.path.join(self.user_profile['dataDir'], 'bluetoothpairing', 'persistence.json')

        self.running = True
        self.clock_active = False
        self.last_connection_fail_time = 0
        self.poll_counter = 0 # once every 20 UI polls we find out the 'now playing'data. If a play button on the UI is pressed, this counter is also reset.
        self.show_buttons_everywhere = False
        
        self.in_first_run = True;
        self.audio_output_options = []
        self.now_playing = "" # will hold artist and song title
        self.current_stream_has_now_playing_info = True
        self.player = None
        self.get_song_details = True
        self.output_to_both = False
        
        self.clock_active = True  # TODO used to circumvent the clock thread for now, as an experiment
        
        self.respeaker_detected = False
        
        
        # VLC
        self.use_vlc = False
        self.vlc_player = None
        self.previous_audio_output = None
        #self.vlc_current_output = 'default'
        self.vlc_devices = {}
       
        
        
        vlc_check_output = run_command('which vlc')
        if '/vlc' in vlc_check_output:
            self.use_vlc = True
            
            
        if self.use_vlc:
            print("VLC detected")
            self.vlc_player = vlc.MediaPlayer()
            #self.vlc_current_output = self.vlc_player.audio_output_device_get()

            mods = self.vlc_player.audio_output_device_enum()
            if mods:
                index = 0
                mod = mods
                while mod:
                    mod = mod.contents
                    desc = mod.description.decode('utf-8', 'ignore')
                    dev = mod.device.decode('utf-8', 'ignore')
                    
                    print(f'index = {index}, desc = {desc}, device = {dev}')
                    
                    if desc == 'Default':
                        self.vlc_devices['Automatic'] = dev
                        
                    elif 'eadphone' in desc and 'sysdefault' in dev:
                        self.vlc_devices['Headphone jack'] = dev
                        
                    elif ('hdmi-0' in desc or 'HDMI 0' in desc or 'HDMI0' in desc) and 'sysdefault' in dev:
                        self.vlc_devices['HDMI 0'] = dev
                        
                    elif ('hdmi-1' in desc or 'HDMI 1' in desc or 'HDMI1' in desc) and 'sysdefault' in dev:
                        self.vlc_devices['HDMI 1'] = dev
                        
                    elif 'luetooth' in desc:
                        self.vlc_devices['Bluetooth speaker'] = dev

                    mod = mod.next
                    index += 1
                
                #print("self.vlc_output_device_ids: " + str(self.vlc_output_device_ids))
                print("VLC audio output devices: " + str(self.vlc_devices))
            
            
        else:
            print("VLC not detected")
        
        
        # Bluetooth
        self.last_bt_connection_check_time = 0
        self.bluealsa_available = False
        try:
            bluealsa_check_output = run_command('aplay -L')
            if 'bluealsa' in bluealsa_check_output:
                self.bluealsa_available = True
        except Exception as ex:
            print("error checking for bluealsa: " + str(ex))
            
            
        # Get audio output options
        if sys.platform != 'darwin':
            self.audio_controls = get_audio_controls()
            #print(self.audio_controls)
            # create list of human readable audio-only output options
            
            for option in self.audio_controls:
                self.audio_output_options.append( option['human_device_name'] )

            if self.bluealsa_available:
                self.audio_output_options.append( "Bluetooth speaker" )
                
            respeaker_check = run_command('aplay -l') 
            if 'seeed' in respeaker_check:
                self.respeaker_detected = True
                if self.DEBUG:
                    print("respeaker hat detected, will use ffplay instead of omxplayer")

        # Get persistent data
        try:
            with open(self.persistence_file_path) as f:
                self.persistent_data = json.load(f)
                if self.DEBUG:
                    print('self.persistent_data loaded from file: ' + str(self.persistent_data))
                try:
                    if 'audio_output' not in self.persistent_data:
                        if self.DEBUG:
                            print("audio output was not in persistent data, adding it now.")
                        if len(self.audio_controls) > 0:
                            self.persistent_data['audio_output'] = str(self.audio_controls[0]['human_device_name'])
                        else:
                            self.persistent_data['audio_output'] = ""
                except:
                    print("Error fixing audio output in persistent data")
                
                try:
                    if 'stations' not in self.persistent_data:
                        if self.DEBUG:
                            print("stations was not in persistent data, adding it now.")
                        self.persistent_data['stations'] = []
                except:
                    print("Error fixing missing stations in persistent data")
                
                try:
                    if 'current_stream_url' not in self.persistent_data:
                        if self.DEBUG:
                            print("current_stream_url was not in persistent data, adding it now.")
                        self.persistent_data['current_stream_url'] = 'http://direct.fipradio.fr/live/fip-midfi.mp3';
                except:
                    print("Error fixing missing stations in persistent data")
                
                if self.DEBUG:
                    print("Persistence data was loaded succesfully.")
                    
                    
        except:
            if self.DEBUG:
                print("Could not load persistent data (if you just installed the add-on then this is normal)")
            try:
                first_audio_output = ""
                if len(self.audio_controls) > 0:
                    if 'human_device_name' in self.audio_controls[0]:
                        first_audio_output = self.audio_controls[0]['human_device_name']
                self.persistent_data = {'power':False,'station':'FIP','volume':100, 'audio_output':  first_audio_output, 'stations':[{'name':'FIP','stream_url':'http://direct.fipradio.fr/live/fip-midfi.mp3'}] }
            
            except Exception as ex:
                print("Error in handling missing persistent data file: " + str(ex))
                self.persistent_data = {'power':False,'station':'FIP','volume':100, 'audio_output': "", 'stations':[{'name':'FIP','stream_url':'http://direct.fipradio.fr/live/fip-midfi.mp3'}] }


        # LOAD CONFIG

        # self.persistent_data['current_stream_url'] = None
        self.radio_stations_names_list = []

        try:
            self.add_from_config()

        except Exception as ex:
            print("Error loading config: " + str(ex))

        if 'playing' not in self.persistent_data:
            self.persistent_data['playing'] = False

        if 'bluetooth_device_mac' not in self.persistent_data:
            self.persistent_data['bluetooth_device_mac'] = None
            
        if 'current_stream_url' not in self.persistent_data:
            self.persistent_data['current_stream_url'] = None


        # Start the API handler
        try:
            if self.DEBUG:
                print("starting api handler")
            self.api_handler = InternetRadioAPIHandler(self, verbose=True)
            #self.manager_proxy.add_api_handler(self.extension)
            if self.DEBUG:
                print("Extension API handler initiated")
        except Exception as e:
            if self.DEBUG:
                print("Failed to start API handler (this only works on gateway version 0.10 or higher). Error: " + str(e))


        # Give Bluetooth Pairing addon some time to reconnect to the speaker
        if self.persistent_data['bluetooth_device_mac'] != None:
            if not self.DEBUG:
                time.sleep(15)
        
        if self.bluetooth_device_check():
            if self.DEBUG:
                print("Bluetooth output device seems to be available (in theory)")
        
        #if self.DEBUG:
        if self.DEBUG:
            print("complete legacy self.audio_output_options : " + str(self.audio_output_options))
        
        # Create the radio device
        try:
            internet_radio_device = InternetRadioDevice(self, self.radio_stations_names_list, self.audio_output_options)
            self.handle_device_added(internet_radio_device)
            if self.DEBUG:
                print("internet_radio_device created")
            self.devices['internet-radio'].connected = True
            self.devices['internet-radio'].connected_notify(True)

        except Exception as ex:
            print("Could not create internet_radio_device: " + str(ex))


        self.player = None


        # temporary change until VLC is implemented
        if os.path.isfile('/boot/candle_original_version.txt'):
            self.respeaker_detected = True
        # Restore volume
        #try:
        #    self.set_audio_volume(self.persistent_data['volume'])
        #except Exception as ex:
        #    print("Could not restore radio station: " + str(ex))


        # Restore station
        try:
            if self.persistent_data['station'] != None:
                if self.DEBUG:
                    print("Setting radio station to the one found in persistence data: " + str(self.persistent_data['station']))
                self.set_radio_station(self.persistent_data['station'])
            else:
                if self.DEBUG:
                    print("No radio station was set in persistence data")
        except Exception as ex:
            print("couldn't set the radio station name to what it was before: " + str(ex))


        # Restore power
        try:
            self.set_radio_state(bool(self.persistent_data['power']))
        except Exception as ex:
            print("Could not restore radio station: " + str(ex))

        #print("internet radio adapter init complete")


        self.ready = True



        defunct_count = 0
        
        while self.running: # and self.player != None
            time.sleep(1)
        
            if self.persistent_data['playing'] == True:
                #if self.DEBUG:
                #    print(str(self.adapter.poll_counter))
                
                # done this way to immediately call get_artist when the player starts
                if self.poll_counter == 0:
                    if self.get_song_details:
                        self.now_playing = self.get_artist()
                
                #if self.adapter.playing:
                self.poll_counter += 1
                if self.poll_counter > 20:
                    self.poll_counter = 0
                
                # Every 3 seconds check if the music player hasn't crashed. If this seems the case twice in a row, restart the player
                if self.poll_counter % 3 == 0:
                    defunct_check = run_command("ps aux | grep 'omxplayer'")
        
                    if "[omxplayer] <defunct>" in defunct_check:
                        if self.DEBUG:
                            print("omx player may have crashed, spotted 'defunct'")
        
                        defunct_count += 1
            
                        if defunct_count > 1:
                            if self.DEBUG:
                                print("spotted 'defunct' twice in a row. Restarting crashed omx player")
                            defunct_count = -5
                            self.set_radio_state(True)
                    else:
                        defunct_count = 0
                
            else:
                defunct_count = 0

        
            
            



    def add_from_config(self):
        """Attempt to add all configured devices."""
        try:
            database = Database(self.addon_name)
            if not database.open():
                print("Error. Could not open settings database")
                return

            config = database.load_config()
            database.close()

        except:
            print("Error. Failed to open settings database.")
            return
            
        try:
            if not config:
                print("Error, no config data available")
                return

            if 'Debugging' in config:
                #print("-Debugging was in config")
                self.DEBUG = bool(config['Debugging'])
                if self.DEBUG:
                    print("Debugging enabled")

            if self.DEBUG:
                print(str(config))
                
            if 'Show buttons everywhere' in config:
                #print("-Debugging was in config")
                self.show_buttons_everywhere = bool(config['Show buttons everywhere'])
                if self.DEBUG:
                    print("Show buttons everywhere preference was in config: " + str(self.show_buttons_everywhere))

            if 'Do not get song details' in config:
                #print("-Debugging was in config")
                self.get_song_details = not bool(config['Do not get song details'])
                if self.DEBUG:
                    print("Do not get song details preference was in config: " + str(not self.get_song_details))

            if "Output music to both ports" in config:
                self.output_to_both = bool(config['Output music to both ports'])
                if self.DEBUG:
                    print("Output music to both ports preference was in config: " + str(self.output_to_both))

            if "Use FFPlay instead of OMX Player" in config:
                ffplay_preference = bool(config['Use FFPlay instead of OMX Player'])
                if ffplay_preference:
                    self.respeaker_detected = ffplay_preference
                if self.DEBUG:
                    print("Use FFPlay instead of OMX Player preference was in config. self.respeaker_detected is now: " + str(self.respeaker_detected))

            if 'Radio stations' in config and len(self.persistent_data['stations']) == 0:
                self.persistent_data['stations'] = config['Radio stations']
                if self.DEBUG:
                    print("self.persistent_data['stations'] was in config. It has not been moved to persistent data.")

        except Exception as ex:
            print("Error in add_from_config: " + str(ex))






        



    def bluetooth_device_check(self):
        if self.DEBUG:
            print("checking if bluetooth speaker is connected")
        
        try:
            
            aplay_pcm_check = run_command('aplay -L')
            if self.DEBUG:
                print("aplay_pcm_check: " + str(aplay_pcm_check))
                
            if 'bluealsa' in aplay_pcm_check:
                self.bluealsa = True
                if self.DEBUG:
                    print("BlueAlsa was detected as PCM option")
                    
                if self.persistent_data['bluetooth_device_mac'] != None:
                    bluetooth_check = run_command('sudo bluetoothctl info ' + self.persistent_data['bluetooth_device_mac'])
                    if 'Icon: audio-card' in bluetooth_check and 'Connected: yes' in bluetooth_check:
                        return True

                # if the current mac wasn't connected, check with the Bluetooth Pairing addon for updated information.
                with open(self.bluetooth_persistence_file_path) as f:
                    self.bluetooth_persistent_data = json.load(f)
                    if self.DEBUG:
                        print("Bluetooth persistence data was loaded succesfully: " + str(self.bluetooth_persistent_data))
                    
                    if 'connected' in self.bluetooth_persistent_data: # grab the first connected speaker we find
                        if len(self.bluetooth_persistent_data['connected']) > 0:
                            for bluetooth_device in self.bluetooth_persistent_data['connected']:
                                if self.DEBUG:
                                    print("checking connected device: " + str(bluetooth_device))
                                if "type" in bluetooth_device and "address" in bluetooth_device:
                                    if bluetooth_device['type'] == 'audio-card':
                                        if self.DEBUG:
                                            print("bluetooth device is audio card")
                                        self.persistent_data['bluetooth_device_mac'] = bluetooth_device['address']
                                        self.save_persistent_data()
                                        if not "Bluetooth speaker" in self.audio_output_options:
                                            self.audio_output_options.append( "Bluetooth speaker" )
                                        return True
                        else:
                            if self.DEBUG:
                                print("No connected devices found in persistent data from bluetooth pairing addon")
                
            else:
                if self.DEBUG:
                    print('bluealsa is not installed, bluetooth audio output is not possible')
                                
                        
        except Exception as ex:
            print("Bluetooth pairing addon check error: " + str(ex))
            
        self.persistent_data['bluetooth_device_mac'] = None
        #self.save_persistent_data()
        return False



    def get_artist(self):
        info = ''
        self.poll_counter += 1
            
        try:
            url = self.persistent_data['current_stream_url']
            encoding = 'latin1'
            
            if not self.persistent_data['playing']:
                self.set_artist_on_thing(None)
                self.set_song_on_thing(None)
                return ""
                
            if self.current_stream_has_now_playing_info == False:
                return
                
            #if self.DEBUG:
            #    print("in get_artist (a.k.a. get now_playing), with url: " + str(url))

            """
            if url is not self.previous_station_url:
            
                if self.radio_session != None:
                    print("radio session already existed")

                else:
                    print('creating radio_session')
                    self.radio_session = requests.Session()
            """
        
            """
            #verb = 'POST'
            response = requests.request('STATS', headers={'Icy-MetaData': '1'},
                 url=url,
                 stream=True
                 #data={"type":record[0], "name":record[1], "content":record[2]}
                 )
            
            
            
            verb = 'POST'
            response = requests.request(verb, headers=self.auth,
                 url=self.API + '/zones/' + str(zID) + '/dns_records',
                 data={"type":record[0], "name":record[1], "content":record[2]}
            )
            
            
            print('response: ' + str(response))
            """
            
            radio_session = requests.Session()

            radio = radio_session.get(url, headers={'Icy-MetaData': '1'}, stream=True)

            try:
                metaint = int(radio.headers['icy-metaint'])
                
            except Exception as ex:
                return

            stream = radio.raw
            #print("stream: " + str(stream))

            audio_data = stream.read(metaint)
            meta_byte = stream.read(1)


            radio_session.close()
            
            if (meta_byte):
                meta_length = ord(meta_byte) * 16

                meta_data = stream.read(meta_length).rstrip(b'\0')

                #print("meta data: " + str(meta_data))

                #stream_title = re.search(br"StreamTitle='([^']*)';", meta_data)
                stream_title = re.search(br"StreamTitle='([^;]*)';", meta_data)
            

                if stream_title:
                    if self.DEBUG:
                        print("stream title: " + str(stream_title))
                    stream_title = stream_title.group(1).decode(encoding, errors='replace')

                    if info != stream_title:
                        
                        if any(c.isalpha() for c in stream_title) and len(stream_title) > 6:
                            
                            stream_title=re.sub("\[.*?\]","",stream_title) # remove info between square btrackets
                                           
                            
                            both = stream_title.split(' - ', maxsplit=1)
                            
                            if len(both) == 2:
                                artist = both[0]
                                song = both[1]
                            else:
                                artist = None
                                song = stream_title

                            if len(song) > 20:
                                song=re.sub("\(.*?\)","",song) # if the string is still quite long, also remove everything in between curly brackets.
                            
                            self.set_artist_on_thing(artist)
                            self.set_song_on_thing(song)
                            
                            if len(stream_title) > 20:
                                stream_title=re.sub("\(.*?\)","",stream_title)
                            info = stream_title
                            

                    else:
                        pass
                        
                else:
                    self.set_song_on_thing(None)
                    self.set_artist_on_thing(None)
                    self.current_stream_has_now_playing_info = False # avoid continuously polling a station that doesn't provide now_playing information
            
        except Exception as ex:
            print("Error in get_artist: " + str(ex))
        
        #if self.DEBUG:
        #    print('get_artist >> Now playing: ', info)
        return info
            
            
            
            
            




#
# MAIN SETTING OF THE RADIO STATES
#

    def set_radio_station(self, station_name):
        if self.DEBUG:
            print("Setting radio station to: " + str(station_name))
            
        try:
            if station_name.startswith('http'): # override to play a stream without a name
                url = station_name
                if self.DEBUG:
                    print("a stream was provided instead of a name")
                for station in self.persistent_data['stations']:
                    if station['stream_url'] == station_name: # doing an ugly swap,
                        if self.DEBUG:
                            print("station name reversed match")
                        station_name = station['name']
                        url = station['stream_url']
                        if str(station_name) != str(self.persistent_data['station']):
                            if self.DEBUG:
                                print("Saving station to persistence data")
                            self.persistent_data['station'] = str(station_name)
                            self.save_persistent_data()
                        
                        if self.DEBUG:
                            print("setting station name on thing")
                        
                        self.set_station_on_thing(str(station['name']))
                        
            else:
                url = ""
                for station in self.persistent_data['stations']:
                    if station['name'] == station_name:
                        #print("station name match")
                        url = station['stream_url']
                        if str(station_name) != str(self.persistent_data['station']):
                            if self.DEBUG:
                                print("Saving station to persistence data")
                            self.persistent_data['station'] = str(station_name)
                            self.save_persistent_data()
                        
                        if self.DEBUG:
                            print("setting station name on thing")
                        
                        self.set_station_on_thing(str(station['name']))
                        
        except Exception as ex:
            print("Error figuring out station: " + str(ex))

        try:
            if url.startswith('http') or url.startswith('rtsp'):
                if self.DEBUG:
                    print("URL starts with http or rtsp")
                if url.endswith('.m3u') or url.endswith('.pls'):
                    if self.DEBUG:
                        print("URL ended with .m3u or .pls (is a playlist): " + str(url))
                    url = self.scrape_url_from_playlist(url)
                    if self.DEBUG:
                        print("Extracted URL = " + str(url))

                self.persistent_data['current_stream_url'] =  url
                self.save_persistent_data()
                
                # get_artist preparation
                self.now_playing = ""
                self.set_song_on_thing(None)
                self.set_artist_on_thing(None)
                self.current_stream_has_now_playing_info = True # reset this, so get_artist will try to get now_playing info
                self.poll_counter = 18 # this will cause get_artist to be called again soon
                
                # Finally, if the station is changed, also turn on the radio (except for the first time)
                if self.in_first_run:
                    self.in_first_run = False
                    if self.DEBUG:
                        print("Set first_run to false")
                else:
                    if self.DEBUG:
                        print("Station changed. Next: turning on the radio\n")
                    self.set_radio_state(True)
                
            else:
                self.set_status_on_thing("Not a valid URL")
        except Exception as ex:
            print("Error handling playlist file: " + str(ex))




    def set_radio_state(self,power,also_call_volume=True):
        if self.DEBUG:
            print("in set_radio_state. Setting radio power to: " + str(power))
        
        if self.running == False:
            if self.DEBUG:
                print("tried to restart during unload?")
            return
            
        try:
            if self.DEBUG:
                print("self.persistent_data['power'] in set_radio_state: " + str(self.persistent_data['power']))
            if bool(power) != bool(self.persistent_data['power']):
                if self.DEBUG:
                    print("radio state changed from value in persistence.")
                self.persistent_data['power'] = bool(power)
                if self.DEBUG:
                    print("self.persistent_data['power'] = power? " + str(self.persistent_data['power']) + " =?= " + str(power))
                self.save_persistent_data()
            else:
                if self.DEBUG:
                    print("radio state same as value in persistence.")

                #if power:
                #    if self.player != None:
                #        self.player.terminate()
                #        self.player.kill()

            #
            #  turn on
            #
            if power:
                
                environment = os.environ.copy()
                
                # Checking audio output option
                
                bt_connected = False
                
                try:
                    if self.DEBUG:
                        print("self.persistent_data['audio_output']: " + str(self.persistent_data['audio_output']))
                    
                    
                    # Check if a bluetooth speaker is connected
                    if self.persistent_data['audio_output'] == 'Bluetooth speaker':
                        if self.DEBUG:
                            print("Doing bluetooth speaker connection check")
                        
                        
                        bluetooth_connection_check_output = run_command('amixer -D bluealsa scontents')
                        if len(bluetooth_connection_check_output) > 10:
                            bt_connected = True
                    
                        # Find out if another speaker was paired/connected through the Bluetooth Pairing addon
                        else:
                            if self.DEBUG:
                                print("Bluetooth device mac was None. Doing bluetooth_device_check")
                            if self.bluetooth_device_check():
                                if self.persistent_data['bluetooth_device_mac'] != None:
                                    bt_connected = True
                            else:
                                self.send_pairing_prompt("Please (re)connect a Bluetooth speaker using the Bluetooth pairing addon")
                                if self.DEBUG:
                                    print("bluetooth_device_check: no connected speakers?")
                    
                        if bt_connected:
                            if self.DEBUG:
                                print("Bluetooth speaker seems to be connected")
                            #environment["SDL_AUDIODRIVER"] = "alsa"
                            #environment["AUDIODEV"] = "bluealsa:" + str(self.persistent_data['bluetooth_device_mac'])
                            
                            
                            
                    elif sys.platform != 'darwin':
                            for option in self.audio_controls:
                                if self.DEBUG:
                                    print( str(option['human_device_name']) + " =?= " + str(self.persistent_data['audio_output']) )
                                if option['human_device_name'] == str(self.persistent_data['audio_output']):
                                    if self.DEBUG:
                                        print("setting ALSA_CARD environment variable to: " + str(option['simple_card_name']))
                                    environment["ALSA_CARD"] = str(option['simple_card_name'])
                                    
                                    
                    # TODO: provide the option to fall back to normal speakers if the bluetooth speaker is disconnected?
                                    
                except Exception as ex:
                    print("Error in set_radio_state while doing audio output (bluetooth speaker) checking: " + str(ex))
                
                
                
                
                
                if self.use_vlc:
                    
                    if self.persistent_data['audio_output'] != self.previous_audio_output:
                        self.vlc_player.stop()
                        
                        if str(self.persistent_data['audio_output']) in self.vlc_devices:
                            
                            # Initial audio output
                            new_audio_output_device = self.vlc_devices[str(self.persistent_data['audio_output'])]
                            if self.DEBUG:
                                print("Initial new audio output: " + str(new_audio_output_device))
                            
                            # Check if the Bluetooth speaker should be selected or de-selected
                            bluetooth_speaker_connected = False
                            if str(self.persistent_data['audio_output']) == 'Bluetooth speaker' or str(self.persistent_data['audio_output']) == 'Automatic':
                                bluetooth_speaker_connected = self.bluetooth_device_check()
                            
                            # Bluetooth speaker selected, but it's not connected
                            if str(self.persistent_data['audio_output']) == 'Bluetooth speaker' and bluetooth_speaker_connected == False:
                                self.send_pairing_prompt("Please (re)connect a Bluetooth speaker using the Bluetooth pairing addon")
                                if self.DEBUG:
                                    print("bluetooth_device_check: no connected speakers?")
                                
                                if 'Automatic' in self.vlc_devices:
                                    new_audio_output_device = self.vlc_devices['Automatic']
                                else:
                                    if self.DEBUG:
                                        print("No Bluetooth speaker connected, and could not fall back to Default either")
                                    return
                            
                            # Automatic, and a Bluetooth speaker is connected
                            elif str(self.persistent_data['audio_output']) == 'Automatic' and bluetooth_speaker_connected == True:
                                new_audio_output_device = self.vlc_devices['Bluetooth speaker']
                            
                            
                            # Set the new audio putput
                            if self.DEBUG:
                                print("Switching VLC to new audio output: " + str(new_audio_output_device))
                            self.vlc_player.audio_output_device_set(None, new_audio_output_device)
                            
                        else:
                            if self.DEBUG:
                                print("could not change VLC audio output, invalid value: " + str(self.persistent_data['audio_output']) )
                        
                    self.previous_audio_output = self.persistent_data['audio_output']
                
                    self.vlc_player.audio_set_volume( self.persistent_data['volume'] )
                    self.vlc_media = vlc.Media( str(self.persistent_data['current_stream_url']) )
                
                    # setting media to the media player
                    self.vlc_player.set_media( self.vlc_media )
                    if self.DEBUG:
                        print("turning on VLC")
                    # start playing video
                    self.vlc_player.play()

                    time.sleep(1)
                    self.set_audio_volume(self.persistent_data['volume'])
                
                
                # NOT VLC
                else:
                    
                    
                    
                    
                    if self.player != None:
                        if self.DEBUG:
                            print("set_radio_state: warning, the player already existed. Stopping it first.")
                        try:
                            if self.respeaker_detected == False:
                                self.player.stdin.write(b'q')
                            self.player.terminate()
                            self.player = None
                        except Exception as ex:
                            print("error terminating omxplayer with Q command. Maybe it stopped by itself?: " + str(ex))
                            print("player.poll(): " + str( self.player.poll() ))
                            #self.player = None
                
                    else:
                        if self.DEBUG:
                            print("self.player was still None")
                         
                    #if self.respeaker_detected:
                    if self.DEBUG:
                        print("pkill omxplayer")
                    os.system('pkill omxplayer')
                    
                
                    if self.DEBUG:
                        print("pkill ffplay")
                    os.system('pkill ffplay')
                
                    self.player = None
                    
                    
                    
                    #kill_process('ffplay')
                
				
                    logarithmic_volume = -6000 # start at 0
				
                    # set the volume by starting omx-player with that volume
                    # Somehow this volume doesn't match the volume from the set_audio_volume method, so it's a fall-back option.
                    if also_call_volume == False and self.respeaker_detected == False:
                    
                        if self.persistent_data['volume'] > 0:
                        	#print("volume is now 1")
                            pre_volume = int(self.persistent_data['volume']) / 100
        					#print("pre_volume: " + str(pre_volume))
        					# OMXPlayer volume is between -6000 and 0 (logarithmic)
                            logarithmic_volume = 2000 * math.log(pre_volume)
        					#print("logarithmic_volume: " + str(logarithmic_volume))
                
               
                
                    try:
                        if self.respeaker_detected:
                    
                            if bt_connected:
                    
                                environment["SDL_AUDIODRIVER"] = "alsa"
                                #environment["AUDIODEV"] = "bluealsa:" + str(self.persistent_data['bluetooth_device_mac'])
                                environment["AUDIODEV"] = "bluealsa:00:00:00:00:00:00"
                    
                                #my_command = "SDL_AUDIODRIVER=alsa UDIODEV=bluealsa:DEV=" + str(self.persistent_data['bluetooth_device_mac']) + " ffplay -nodisp -vn -infbuf -autoexit -volume " + str(self.persistent_data['volume']) + " " + str(self.persistent_data['current_stream_url'])
                                my_command = "ffplay -nodisp -vn -infbuf -autoexit -volume " + str(self.persistent_data['volume']) + " " + str(self.persistent_data['current_stream_url'])
                    
                    
                                if self.DEBUG:
                                    print("Internet radio addon will call this subprocess command: " + str(my_command))
                                    print("starting ffplay...")
                                self.player = subprocess.Popen(my_command, 
                                                env=environment,
                                                shell=True,
                                                stdin=subprocess.PIPE,
                                                stdout=subprocess.PIPE,
                                                stderr=subprocess.PIPE)
                
                
                            else:
                                #my_command = "ffplay -nodisp -vn -infbuf -autoexit" + str(self.persistent_data['current_stream_url']) + " -volume " + str(self.persistent_data['volume'])
                                my_command = ("ffplay", "-nodisp", "-vn", "-infbuf","-autoexit","-volume",str(self.persistent_data['volume']), str(self.persistent_data['current_stream_url']) )

                                if self.DEBUG:
                                    print("Internet radio addon will call this subprocess command: " + str(my_command))
                                    print("starting ffplay...")
                                self.player = subprocess.Popen(my_command, 
                                                env=environment,
                                                stdin=subprocess.PIPE,
                                                stdout=subprocess.PIPE,
                                                stderr=subprocess.PIPE)
                    
                        else:
                    
                            #if self.persistent_data['audio_output'] == 'Built-in headphone jack':
                            #    omx_output = "local"
                            #else:
                            #    omx_output = "hdmi"
                    
                        
                    
                            omx_output = "alsa:sysdefault"
                
                            if self.output_to_both:
                                omx_output = "both"
                
                            if bt_connected:
                                omx_output = "alsa:bluealsa"
			
                            omx_command = "omxplayer -o " + str(omx_output) + " --vol " + str(logarithmic_volume) + " -z --audio_queue 10 --audio_fifo 10 --threshold 5 " + str(self.persistent_data['current_stream_url'])
                            if self.DEBUG:
                                print("\nOMX Player command: " + str(omx_command))
                            #omxplayer -o alsa:bluealsa
            
                            command_array = omx_command.split(' ')
            
                            environment = os.environ.copy()
                            environment["DISPLAY"] = ":0"
                            environment["LD_LIBRARY_PATH"] = "/opt/vc/lib"
                    
                            self.player = subprocess.Popen(command_array, 
                                                env=environment,
                                                stdin=subprocess.PIPE,
                                                stdout=subprocess.PIPE,
                                                stderr=subprocess.PIPE,
                                                bufsize=0,
                                                close_fds=True)
                                                
                                        
                            self.set_audio_volume(self.persistent_data['volume'])
                
                    
                
                        if self.DEBUG:
                            print("self.player created")
                    
                
                        if also_call_volume and self.respeaker_detected == False and self.use_vlc == False:
                            if self.DEBUG:
                                print("set_radio_state: alse setting volume")
                            time.sleep(1)
                            self.set_audio_volume(self.persistent_data['volume'])
                    
                    except Exception as ex:
                        if self.DEBUG:
                            print("Error starting audio player: " + str(ex))
                        
                        
                        
                self.persistent_data['playing'] = True
                self.set_status_on_thing("Playing")
                
     
            #
            #  turn off
            #
            else:
                if self.DEBUG:
                    print("turning off radio")
                try:
                    self.persistent_data['playing'] = False
                    self.set_status_on_thing("Stopped")
                    self.get_artist() # sets now_playing data to none on the device and UI
                    
                    
                    if self.use_vlc:
                    
                        self.vlc_player.audio_set_volume( self.persistent_data['volume'] )
                        self.vlc_media = vlc.Media( str(self.persistent_data['current_stream_url']) )
                    
                        # setting media to the media player
                        self.vlc_player.set_media( self.vlc_media )

                        if self.DEBUG:
                            print("turning off VLC")
                        # start playing video
                        self.vlc_player.stop()
                    
                    else:
                        if self.player != None:
                            if self.DEBUG:
                                print("player object existed")
                            if self.respeaker_detected == False:
                                self.player.stdin.write(b'q')
                                self.player.stdin.flush()
                            self.player.terminate()
                            self.player.kill()
                            #os.system('pkill ffplay')
                            if self.respeaker_detected:
                                os.system('pkill ffplay')
                            else:
                                os.system('pkill omxplayer')
                            self.player = None
                
                        else:
                            if self.DEBUG:
                                print("Could not stop the player because it wasn't running.")
                                
                except Exception as ex:
                    if self.DEBUG:
                        print("Error stopping audio player: " + str(ex))
                
                
            # update the UI
            self.set_state_on_thing(bool(power))

        except Exception as ex:
            if self.DEBUG:
                print("Error setting radio state: " + str(ex))



    def set_audio_volume(self,volume):
        if self.DEBUG:
            print("Setting audio output volume to " + str(volume))
            print("self.player: " + str(self.player))
        
        set_volume_via_radio_state = False   
        
        if int(volume) != self.persistent_data['volume']:
            self.persistent_data['volume'] = int(volume)
            self.save_persistent_data()
            if self.DEBUG:
                print("Volume changed")
        else:
            if self.DEBUG:
                print("Volume did not change")
                
                
        if self.use_vlc:
            if self.DEBUG:
                print("setting VLC volume")
            self.vlc_player.audio_set_volume( self.persistent_data['volume'] )
        
        else:
             
            if self.respeaker_detected:
                set_volume_via_radio_state = True # changes volume by completely restarting the player and giving it the new initial volume value
                if self.DEBUG:
                    print("set_audio_volume: set_volume_via_radio_state is true")
            
        
                
            try:
                if self.player != None and self.respeaker_detected == False:
                
                    if self.DEBUG:
                        print("Trying dbus volume")

                    omxplayerdbus_user = run_command('cat /tmp/omxplayerdbus.${USER:-root}')
                    if self.DEBUG:
                        print("DBUS_SESSION_BUS_ADDRESS: " + str(omxplayerdbus_user))
                    environment = os.environ.copy()
                    if omxplayerdbus_user != None:
                        if self.DEBUG:
                            print("trying dbus-send")
                        environment["DBUS_SESSION_BUS_ADDRESS"] = str(omxplayerdbus_user).strip()
                        environment["DISPLAY"] = ":0"
                
                        #if self.DEBUG:
                        #    print("environment: " + str(environment))
                    
                        dbus_volume = volume / 100
                        if self.DEBUG:
                            print("dbus_volume: " + str(dbus_volume))
                    
                        dbus_command = 'dbus-send --print-reply --session --reply-timeout=500 --dest=org.mpris.MediaPlayer2.omxplayer /org/mpris/MediaPlayer2 org.freedesktop.DBus.Properties.Set string:"org.mpris.MediaPlayer2.Player" string:"Volume" double:' + str(dbus_volume)
                        #export DBUS_SESSION_BUS_ADDRESS=$(cat /tmp/omxplayerdbus.${USER:-root})
                        dbus_process = subprocess.Popen(dbus_command, 
                                        env=environment,
                                        shell=True,				# Streaming to bluetooth seems to only work if shell is true. The position of the volume string also seemed to matter
                                        stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE,
                                        close_fds=True)
                
                        stdout,stderr = dbus_process.communicate()
                        if len(stderr) > 4:
                            set_volume_via_radio_state = True
                        else:
                            set_volume_via_radio_state = False
                    
                        if self.DEBUG:
                            print("dbus stdout: " + str(stdout))
                            print("dbus stderr: " + str(stderr))
                
                        #dbus_result = dbus_process.stdout.read()
                        #dbus_process.stdout.close()
                
                
                
                        # Check that omxplayer wasn't doubled..
                        ps = run_command("ps -aux | grep '/usr/bin/omxplayer.bin'")
                        #ps = run_command('ps -ef | grep omxplayer | grep /bin/bash')

                        processes = ps.split('\n')

                        omx_count = 0
                        nfields = len(processes[0].split()) - 1
                        for row in processes[1:]:
                            if 'grep' in row:
                                #print("skipping grep line")
                                continue
                            #print(" -->  " + str(row))
                            parts = row.split(None, nfields)
                        
                            if omx_count > 0:
                                #print("parts[1]: " + str(parts))
                                if len(parts) > 0:
                                    if self.DEBUG:
                                        print("TOO MANY OMX PLAYERS. Killing one.")
                                    run_command('kill -9 ' + str(parts[1]))
                            
                            if 'defunct' not in row:
                                omx_count += 1
            
                else:
                    self.set_radio_state(self.persistent_data['power'],False)
                    
            except Exception as ex:
                if self.DEBUG:
                    print("Error trying to set volume via dbus: " + str(ex))
                set_volume_via_radio_state= True
            
        self.set_volume_on_thing(volume)
        #if self.player == None:
        
        if set_volume_via_radio_state:
            if self.DEBUG:
                print("WARNING: setting radio volume by restarting audio player instead")
            #self.set_radio_state(self.persistent_data['power'],False)

        return



    



#
# SUPPORT METHODS
#

    def set_status_on_thing(self, status_string):
        if self.DEBUG:
            print("new status on thing: " + str(status_string))
        try:
            if self.devices['internet-radio'] != None:
                #self.devices['internet-radio'].properties['status'].set_cached_value_and_notify( str(status_string) )
                self.devices['internet-radio'].properties['status'].update( str(status_string) )
        except:
            print("Error setting status on internet radio device")


    def set_song_on_thing(self, song_string):
        #if self.DEBUG:
        #    print("new song on thing: " + str(song_string))
        try:
            if self.devices['internet-radio'] != None:
                #self.devices['internet-radio'].properties['status'].set_cached_value_and_notify( str(status_string) )
                self.devices['internet-radio'].properties['song'].update( str(song_string) )
        except:
            print("Error setting song on internet radio device")


    def set_artist_on_thing(self, artist_string):
        #if self.DEBUG:
        #    print("new artist on thing: " + str(artist_string))
        try:
            if self.devices['internet-radio'] != None:
                #self.devices['internet-radio'].properties['status'].set_cached_value_and_notify( str(status_string) )
                self.devices['internet-radio'].properties['artist'].update( str(artist_string) )
        except:
            print("Error setting artist on internet radio device")



    def set_state_on_thing(self, power):
        if self.DEBUG:
            print("new state on thing: " + str(power))
        try:
            if self.devices['internet-radio'] != None:
                self.devices['internet-radio'].properties['power'].update( bool(power) )
        except Exception as ex:
            print("Error setting power state on internet radio device:" + str(ex))



    def set_station_on_thing(self, station):
        if self.DEBUG:
            print("new station on thing: " + str(station))
        try:
            if self.devices['internet-radio'] != None:
                self.devices['internet-radio'].properties['station'].update( str(station) )
        except Exception as ex:
            print("Error setting station on internet radio device:" + str(ex))



    def set_volume_on_thing(self, volume):
        if self.DEBUG:
            print("new volume on thing: " + str(volume))
        try:
            if self.devices['internet-radio'] != None:
                self.devices['internet-radio'].properties['volume'].update( int(volume) )
            else:
                print("Error: could not set volume on internet radio thing, the thing did not exist yet")
        except Exception as ex:
            print("Error setting volume of internet radio device:" + str(ex))



    # Only called on non-darwin devices
    def set_audio_output(self, selection):
        if self.DEBUG:
            print("Setting audio output selection to: " + str(selection))
            
            
            
        if self.use_vlc:
            
            if str(selection) in self.vlc_devices.keys():  #self.vlc_ui_output_devices:
                self.persistent_data['audio_output'] = str(selection)
            else:
                if self.DEBUG:
                    print("invalid audio output selection")
                self.persistent_data['audio_output'] = list(self.vlc_devices.keys())[0]
                
            if self.devices['internet-radio'] != None:
                self.devices['internet-radio'].properties['audio output'].update( str(selection) )
                
            # Restart the radio player
            if self.persistent_data['power']:
                if self.DEBUG:
                    print("restarting radio with new audio output")
                self.set_radio_state(True)
            
            
            
            
        else:
        
            if str(selection) == 'Bluetooth speaker':
                self.persistent_data['audio_output'] = str(selection)
                self.save_persistent_data()
                if self.devices['internet-radio'] != None:
                    self.devices['internet-radio'].properties['audio output'].update( str(selection) )
                if self.persistent_data['power']:
                    if self.DEBUG:
                        print("restarting radio with new audio output")
                    self.set_radio_state(True)
            
            else:
                # Get the latest audio controls
                self.audio_controls = get_audio_controls()
                if self.DEBUG:
                    print(self.audio_controls)
        
                try:        
                    for option in self.audio_controls:
                        if str(option['human_device_name']) == str(selection):
                            if self.DEBUG:
                                print("CHANGING INTERNET RADIO AUDIO OUTPUT")
                            # Set selection in persistence data
                            self.persistent_data['audio_output'] = str(selection)
                            if self.DEBUG:
                                print("persistent_data is now: " + str(self.persistent_data))
                            self.save_persistent_data()
                    
                            if self.DEBUG:
                                print("new selection on thing: " + str(selection))
                            try:
                                if self.DEBUG:
                                    print("self.devices = " + str(self.devices))
                                if self.devices['internet-radio'] != None:
                                    self.devices['internet-radio'].properties['audio output'].update( str(selection) )
                            except Exception as ex:
                                print("Error setting new audio output selection:" + str(ex))
        
                            if self.persistent_data['power']:
                                if self.DEBUG:
                                    print("restarting radio with new audio output")
                                self.set_radio_state(True)
                            break
            
                except Exception as ex:
                    print("Error in set_audio_output: " + str(ex))
        




    def scrape_url_from_playlist(self, url):
        response = requests.get(url)
        data = response.text
        url = None
        #if self.DEBUG:
        #    print("playlist data: " + str(data))
        for line in data.splitlines():
            if self.DEBUG:
                print(str(line))

            if 'http' in line:
                url_part = line.split("http",1)[1]
                if url_part != None:
                    url = "http" + str(url_part)
                    if self.DEBUG:
                        print("Extracted URL: " + str(url))
                    break
                    
        if url == None:
            set_status_on_thing("Error with station")
            
        return url



    def unload(self):
        if self.DEBUG:
            print("Shutting down Internet Radio.")
        self.set_status_on_thing("Bye")
        #self.devices['internet-radio'].connected_notify(False)
        self.save_persistent_data()
        self.set_radio_state(False)
        self.running = False
        #if self.player != None:
        #    self.player.stdin.write(b'q')
        #os.system('pkill omxplayer')


    def remove_thing(self, device_id):
        try:
            self.set_radio_state(False)
            obj = self.get_device(device_id)
            self.handle_device_removed(obj)                     # Remove from device dictionary
            if self.DEBUG:
                print("User removed Internet Radio device")
        except:
            print("Could not remove things from devices")



    def save_persistent_data(self):
        if self.DEBUG:
            print("Saving to persistence data store")

        try:
            if not os.path.isfile(self.persistence_file_path):
                open(self.persistence_file_path, 'a').close()
                if self.DEBUG:
                    print("Created an empty persistence file")
            else:
                if self.DEBUG:
                    print("Persistence file existed. Will try to save to it.")

            with open(self.persistence_file_path) as f:
                if self.DEBUG:
                    print("saving: " + str(self.persistent_data))
                try:
                    json.dump( self.persistent_data, open( self.persistence_file_path, 'w+' ) )
                except Exception as ex:
                    print("Error saving to persistence file: " + str(ex))
                return True
            #self.previous_persistent_data = self.persistent_data.copy()

        except Exception as ex:
            if self.DEBUG:
                print("Error: could not store data in persistent store: " + str(ex) )
            return False







#
# DEVICE
#

class InternetRadioDevice(Device):
    """Internet Radio device type."""

    def __init__(self, adapter, radio_station_names_list, audio_output_list):
        """
        Initialize the object.
        adapter -- the Adapter managing this device
        """

        Device.__init__(self, adapter, 'internet-radio')

        self._id = 'internet-radio'
        self.id = 'internet-radio'
        self.adapter = adapter
        self.DEBUG = adapter.DEBUG

        self.name = 'Radio'
        self.title = 'Radio'
        self.description = 'Listen to internet radio stations'
        self._type = ['MultiLevelSwitch']
        #self.connected = False

        self.radio_station_names_list = radio_station_names_list

        try:
            
            # this will also call handle_device_added
            self.update_stations_property(False)
            
            self.properties["power"] = InternetRadioProperty(
                            self,
                            "power",
                            {
                                '@type': 'OnOffProperty',
                                'title': "Playing",
                                'readOnly': False,
                                'type': 'boolean'
                            },
                            self.adapter.persistent_data['power'])
                            
            self.properties["volume"] = InternetRadioProperty(
                            self,
                            "volume",
                            {
                                '@type': 'LevelProperty',
                                'title': "Volume",
                                'type': 'integer',
                                'readOnly': False,
                                'minimum': 0,
                                'maximum': 100,
                                'unit': 'percent'
                            },
                            self.adapter.persistent_data['volume'])
                            
            self.properties["status"] = InternetRadioProperty(
                            self,
                            "status",
                            {
                                'title': "Status",
                                'type': 'string',
                                'readOnly': True
                            },
                            "Hello")

            self.properties["artist"] = InternetRadioProperty(
                            self,
                            "artist",
                            {
                                'title': "Artist",
                                'type': 'string',
                                'readOnly': True
                            },
                            None)

            self.properties["song"] = InternetRadioProperty(
                            self,
                            "song",
                            {
                                'title': "Song",
                                'type': 'string',
                                'readOnly': True
                            },
                            None)


           
            if sys.platform != 'darwin': #darwin = Mac OS
                if self.DEBUG:
                    print("Adding audio output property")
                    
                selected_output = self.adapter.persistent_data['audio_output']
                if self.DEBUG:
                    print("legacy audio_output_list: " + str(audio_output_list))
                    print("initial selected output: " + str(selected_output))
                    
                try:
                    # Let VLC override everything if it exists
                    if self.adapter.use_vlc == True:
                        if self.DEBUG:
                            print("Using VLC audio output list for audio output property")
                        
                        audio_output_list = list(self.adapter.vlc_devices.keys())
                        if self.DEBUG:
                            print("new VLC audio_output_list : " + str(audio_output_list))
                        if selected_output not in audio_output_list:
                            #if self.DEBUG:
                            
                            selected_output = audio_output_list[0]
                            if self.DEBUG:
                                print("Had to set alternative audio output for property: " + str(selected_output))
                        else:
                            if self.DEBUG:
                                print("ok, selected output was in vlc list")
                except Exception as ex:
                    if self.DEBUG:
                        print("generate vlc audio output list error: " + str(ex))
                
                self.properties["audio output"] = InternetRadioProperty(
                                self,
                                "audio output",
                                {
                                    'title': "Audio output",
                                    'type': 'string',
                                    'readOnly': False,
                                    'enum': audio_output_list,
                                },
                                selected_output)


        except Exception as ex:
            if self.DEBUG:
                print("error adding properties: " + str(ex))

        if self.DEBUG:
            print("Internet Radio thing has been created.")


    # Creates these options "on the fly", as radio stations get added and removed.
    def update_stations_property(self, call_handle_device_added=True):
        #print("in update_stations_property")
        # Create list of radio station names for the radio thing.
        radio_stations_names = []
        for station in self.adapter.persistent_data['stations']:
            if self.DEBUG:
                print("Adding station: " + str(station))
                #print("adding station: " + str(station['name']))
            radio_stations_names.append(str(station['name']))
        
        self.adapter.radio_station_names_list = radio_stations_names
        #print("remaking property? List: " + str(radio_stations_names))
        self.properties["station"] = InternetRadioProperty(
                        self,
                        "station",
                        {
                            'title': "Station",
                            'type': 'string',
                            'enum': radio_stations_names,
                        },
                        self.adapter.persistent_data['station'])
        
        #if call_handle_device_added:
        self.adapter.handle_device_added(self);
        self.notify_property_changed(self.properties["station"])



#
# PROPERTY
#

class InternetRadioProperty(Property):

    def __init__(self, device, name, description, value):
        Property.__init__(self, device, name, description)
        self.device = device
        self.name = name
        self.title = name
        self.description = description # dictionary
        self.value = value
        self.set_cached_value(value)
        self.device.notify_property_changed(self)
        
        #print("property: initiated: " + str(self.name))


    def set_value(self, value):
        #print("property: set_value called for " + str(self.title))
        #print("property: set value to: " + str(value))
        self.set_cached_value(value)
        self.device.notify_property_changed(self)
        
        try:
            if self.title == 'station':
                self.device.adapter.set_radio_station(str(value))
                self.device.adapter.set_radio_state(True) # If the user changes the station, we also play it.
                #self.update(value)

            if self.title == 'power':
                self.device.adapter.set_radio_state(bool(value))
                #self.update(value)

            if self.title == 'volume':
                self.device.adapter.set_audio_volume(int(value))
                #self.update(value)

            if self.title == 'audio output':
                self.device.adapter.set_audio_output(str(value))
                #self.device.adapter.set_radio_state(True) # If the user changes the output, it should switch to that output.


        except Exception as ex:
            print("set_value error: " + str(ex))



    def update(self, value):
        #print("property -> update")
        if value != self.value:
            self.value = value
            self.set_cached_value(value)
            self.device.notify_property_changed(self)





def get_audio_controls():

    audio_controls = []
    
    aplay_result = run_command('aplay -l') 
    lines = aplay_result.splitlines()
    device_id = 0
    previous_card_id = 0
    for line in lines:
        if line.startswith( 'card ' ):
            
            try:
                #print(line)
                line_parts = line.split(',')
            
                line_a = line_parts[0]
                #print(line_a)
                line_b = line_parts[1]
                #print(line_b)
            except:
                continue
            
            card_id = int(line_a[5])
            #print("card id = " + str(card_id))
            
            
            if card_id != previous_card_id:
                device_id = 0
            
            #print("device id = " + str(device_id))
            
            
            simple_card_name = re.findall(r"\:([^']+)\[", line_a)[0]
            simple_card_name = str(simple_card_name).strip()
            
            #print("simple card name = " + str(simple_card_name))
            
            full_card_name   = re.findall(r"\[([^']+)\]", line_a)[0]
            #print("full card name = " + str(full_card_name))
            
            full_device_name = re.findall(r"\[([^']+)\]", line_b)[0]
            #print("full device name = " + str(full_device_name))
            
            human_device_name = str(full_device_name)
            
            # Raspberry Pi 4
            human_device_name = human_device_name.replace("bcm2835 ALSA","Built-in headphone jack")
            human_device_name = human_device_name.replace("bcm2835 IEC958/HDMI","Built-in video")
            human_device_name = human_device_name.replace("bcm2835 IEC958/HDMI1","Built-in video (two)")
            human_device_name = human_device_name.replace("bcm2835 IEC958/HDMI 1","Built-in video (two)")
            
            # Raspberry Pi 3
            human_device_name = human_device_name.replace("bcm2835 Headphones","Built-in headphone jack")
            
            # ReSpeaker dual microphone pi hat
            human_device_name = human_device_name.replace("bcm2835-i2s-wm8960-hifi wm8960-hifi-0","ReSpeaker headphone jack")
            #print("human device name = " + human_device_name)
            
            
            control_name = None
            complex_control_id = None
            complex_max = None
            complex_count = None
            
            amixer_result = run_command('amixer -c ' + str(card_id) + ' scontrols') 
            lines = amixer_result.splitlines()
            
            #print(str(lines))
            #print("amixer lines array length: " + str(len(lines)))
            if len(lines) > 0:
                for line in lines:
                    if "'" in line:
                        #print("line = " + line)
                        control_name = re.findall(r"'([^']+)'", line)[0]
                        #print("control name = " + control_name)
                        if control_name != 'mic':
                            break
                        else:
                            continue # in case the first control is 'mic', ignore it.
                    else:
                        control_name = None
            
            # if there is no 'simple control', then a backup method is to get the normal control options.  
            else:
                
                #print("get audio controls: no simple control found, getting complex one instead")
                #line_counter = 0
                amixer_result = run_command('amixer -c ' + str(card_id) + ' controls')
                lines = amixer_result.splitlines()
                if len(lines) > 0:
                    for line in lines:
                        #line_counter += 1
                        
                        line = line.lower()
                        
                        #print("line.lower = " + line)
                        if "playback" in line:
                            
                            #print("playback spotted")
                            
                            numid_part = line.split(',')[0]
                            
                            if numid_part.startswith("numid="):
                                numid_part = numid_part[6:]

                                #print("numid_part = " + str(numid_part))
                            
                                #complex_max = 36
                                complex_count = 1 # mono
                                complex_control_id = int(numid_part)

                                #print("complex_control_id = " + str(complex_control_id))
                            
                                info_result = run_command('amixer -c ' + str(card_id) + ' cget numid=' + str(numid_part)) #amixer -c 1 cget numid=
                            
                                if 'values=2' in info_result:
                                    complex_count = 2 # stereo
                                
                                info_result_parts = info_result.split(',')
                                for info_part in info_result_parts:
                                    if info_part.startswith('max='):
                                        complex_max = int(info_part[4:])
                                        #complex_max = int(part)
                                        #break
                                        
                                
                            
                            break
                            
                else:
                    print("getting audio volume in complex way failed") 
                            
                            
                
            
                
            if control_name == 'mic':
                control_name = None
            
            audio_controls.append({'card_id':card_id, 
                                'device_id':device_id, 
                                'simple_card_name':simple_card_name, 
                                'full_card_name':str(full_card_name), 
                                'full_device_name':str(full_device_name), 
                                'human_device_name':str(human_device_name), 
                                'control_name':control_name,
                                'complex_control_id':complex_control_id, 
                                'complex_count':complex_count, 
                                'complex_max':complex_max }) # ,'controls':lines


            if card_id == previous_card_id:
                device_id += 1
            
            previous_card_id = card_id

    return audio_controls



def kill_process(target):
    try:
        os.system( "sudo killall " + str(target) )

        #print(str(target) + " stopped")
        return True
    except:

        #print("Error stopping " + str(target))
        return False



def run_command(cmd, timeout_seconds=20):
    try:
        
        p = subprocess.run(cmd, timeout=timeout_seconds, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, universal_newlines=True)

        if p.returncode == 0:
            return p.stdout # + '\n' + "Command success" #.decode('utf-8')
            #yield("Command success")
        else:
            if p.stderr:
                return "Error: " + str(p.stderr) # + '\n' + "Command failed"   #.decode('utf-8'))

    except Exception as e:
        print("Error running command: "  + str(e))
        