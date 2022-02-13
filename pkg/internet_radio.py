"""Internet radio adapter for WebThings Gateway."""

# test command to play radio: 
# ffplay -nodisp -vn -infbuf -autoexit http://direct.fipradio.fr/live/fip-midfi.mp3 -volume 100


import os
import re
import sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib'))
import json
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

        self.running = True
        self.clock_active = False
        self.last_connection_fail_time = 0
        self.poll_counter = 0 # once every 20 UI polls we find out the 'now playing'data. If a play button on the UI is pressed, this counter is also reset.
        self.show_buttons_everywhere = False
        
        self.in_first_run = True;
        self.audio_output_options = []
        self.now_playing = "" # will hold artist and song title
        self.current_stream_has_now_playing_info = True

        # Get audio output options
        if sys.platform != 'darwin':
            self.audio_controls = get_audio_controls()
            #print(self.audio_controls)
            # create list of human readable audio-only output options
            
            for option in self.audio_controls:
                self.audio_output_options.append( option['human_device_name'] )



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
                        if len(self.audio_output_options) > 0:
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
            print("Could not load persistent data (if you just installed the add-on then this is normal)")
            if len(self.audio_output_options) > 0:
                self.persistent_data = {'power':False,'station':'FIP','volume':100, 'audio_output': str(self.audio_controls[0]['human_device_name']), 'stations':[{'name':'FIP','stream_url':'http://direct.fipradio.fr/live/fip-midfi.mp3'}] }
            else:
                self.persistent_data = {'power':False,'station':'FIP','volume':100, 'audio_output': "", 'stations':[{'name':'FIP','stream_url':'http://direct.fipradio.fr/live/fip-midfi.mp3'}] }




            

        # LOAD CONFIG

        self.persistent_data['current_stream_url'] = None
        self.radio_stations_names_list = []

        try:
            self.add_from_config()

        except Exception as ex:
            print("Error loading config: " + str(ex))

        if 'playing' not in self.persistent_data:
            self.persistent_data['playing'] = False


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
            self.close_proxy()

        if not config:
            return

        if 'Debugging' in config:
            #print("-Debugging was in config")
            self.DEBUG = bool(config['Debugging'])
            if self.DEBUG:
                print("Debugging enabled")

        if 'Show buttons everywhere' in config:
            #print("-Debugging was in config")
            self.show_buttons_everywhere = bool(config['Show buttons everywhere'])
            if self.DEBUG:
                print("Show buttons everywhere preference was in config: " + str(self.show_buttons_everywhere))

        

        if self.DEBUG:
            print(str(config))

        try:
            if 'Radio stations' in config and len(self.persistent_data['stations']) == 0:
                self.persistent_data['stations'] = config['Radio stations']
                #self.persistent_data['stations'] = config['Radio stations']
                if self.DEBUG:
                    print("self.persistent_data['stations'] was in config. It has not been moved to persistent data.")

        except Exception as ex:
            print("Error loading radio stations: " + str(ex))





#
#  CLOCK
#

    def clock(self):
        """ Runs every second and handles the various timers """
        if self.DEBUG:
            print("CLOCK INIT. self.player: " + str(self.player))
            print("self.persistent_data['playing']: " + str(self.persistent_data['playing']))
        
        #self.clock_started = True
        self.clock_active = True
        
        while self.clock_active and self.running: # and self.player != None
            time.sleep(1)
            
            if self.persistent_data['playing'] == True:
                try:
                    #if self.DEBUG:
                    #    print(str(self.adapter.poll_counter))
                    if self.poll_counter == 0:
                        self.now_playing = self.get_artist()
                except Exception as ex:
                    print("error updating now_playing: " + str(ex))
            
                #if self.adapter.playing:
                self.poll_counter += 1
                if self.poll_counter > 20:
                    self.poll_counter = 0
            
            
                #print("playing")
                # Wait until process terminates (without using p.wait())
                poll_result = self.player.poll()
                if poll_result is None:
                    #print("playing")
                    pass
                else:
                    time.sleep(1)
                    #print("poll_result: " + str(poll_result))
                    # Get return code from process
                    return_code = self.player.returncode
                    if self.DEBUG:
                        print("clock: self.player process polling return_code: " + str(return_code))
                    if self.persistent_data['playing'] == True:
                        if self.DEBUG:
                            print("Error, radio unexpectedly stopped playing.")
                    
                        self.set_radio_state(True)
                    
                        """
                        if time.time() - self.last_connection_fail_time < 5:
                            if self.DEBUG:
                                print("Already disconnected less than 5 seconds ago too. Something is wrong, turning off radio.")
                            self.set_radio_state(False)
                            self.set_status_on_thing("Could not connect to station")
                            clock_active = False
                        
                        else:
                            self.set_radio_state(True)
                        """
                    
                        self.last_connection_fail_time = time.time()
                        time.sleep(3)
            
                #if self.persistent_data['playing'] == False:
                #    if self.DEBUG:
                #        print("clock noticed that self.persistent_data['playing'] is False. Exiting thread.")
                #    clock_active = False
            
            else:
                self.clock_active = False
            
        if self.DEBUG:
            print("CLOCK THREAD EXIT")









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
                
                # Finally, if the station is changed, also turn on the radio
                if self.in_first_run:
                    self.in_first_run = False
                else:
                    self.set_radio_state(True)
                
            else:
                self.set_status_on_thing("Not a valid URL")
        except Exception as ex:
            print("Error handling playlist file: " + str(ex))




    def set_radio_state(self,power):
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


            #
            #  turn on
            #
            if power:
                self.set_status_on_thing("Playing")
                if self.player != None:
                    if self.DEBUG:
                        print("set_radio_state: warning, the player already existed. Stopping it first.")
                    self.player.terminate()
                    
                environment = os.environ.copy()
                
                
                if sys.platform != 'darwin':
                    for option in self.audio_controls:
                        if self.DEBUG:
                            print( str(option['human_device_name']) + " =?= " + str(self.persistent_data['audio_output']) )
                        if option['human_device_name'] == str(self.persistent_data['audio_output']):
                            environment["ALSA_CARD"] = str(option['simple_card_name'])
                        #else:
                            #print("environment = " + str(environment))
                            
                kill_process('ffplay')
                            
                #my_command = "ffplay -nodisp -vn -infbuf -autoexit" + str(self.persistent_data['current_stream_url']) + " -volume " + str(self.persistent_data['volume'])
                my_command = ("ffplay", "-nodisp", "-vn", "-infbuf","-autoexit", str(self.persistent_data['current_stream_url']),"-volume",str(self.persistent_data['volume']))

                if self.DEBUG:
                    print("Internet radio addon will call this subprocess command: " + str(my_command))
                    print("starting ffplay...")
                self.player = subprocess.Popen(my_command, 
                                env=environment,
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
                
                if self.persistent_data['playing'] == False:
                    try:
                        if hasattr(self, 't'):
                            if self.DEBUG:
                                print("- clock object already existed")
                            if self.t.is_alive():
                                if self.DEBUG:
                                    print("- Weird, clock thread was still alive")
                                time.sleep(3)
                    except Exception as ex:
                        print("Error checking clock thread status: " + str(ex))
                            
                    self.persistent_data['playing'] = True
                            
                else:
                    if self.DEBUG:
                        print("playing was already true, so this was a re-start of a borked ffplay, and the clock thread will not be started again")
                
                
                if self.clock_active == False:
                
                    if self.DEBUG:
                        print("self.persistent_data['playing'] has been set to true. Starting clock thread.")
                    try:
                        self.t = threading.Thread(target=self.clock)
                        self.t.daemon = True
                        self.t.start()
                    except:
                        if self.DEBUG:
                            print("Error starting the clock thread")
                        self.clock_active = False
                
                
                
                """
                try:
                    # Filter stdout
                    for line in iter(p.stdout.readline, ''):
                        sys.stdout.flush()
                        # Print status
                        print(">>> " + line.rstrip())
                        sys.stdout.flush()
                except:
                    sys.stdout.flush()
                """
     
            #
            #  turn off
            #
            else:
                self.persistent_data['playing'] = False
                self.set_status_on_thing("Stopped")
                self.get_artist() # sets now_playing data to none on the device and UI
                if self.player != None:
                    self.player.terminate()
                
                else:
                    if self.DEBUG:
                        print("Could not stop the player because it wasn't running.")
                
            # update the UI
            self.set_state_on_thing(bool(power))

        except Exception as ex:
            print("Error setting radio state: " + str(ex))



    def set_audio_volume(self,volume):
        if self.DEBUG:
            print("Setting audio output volume to " + str(volume))
        if int(volume) != self.persistent_data['volume']:
            self.persistent_data['volume'] = int(volume)
            self.save_persistent_data()

        self.set_volume_on_thing(volume)
        self.set_radio_state(self.persistent_data['power'])
        return



    def get_audio_volume(self):
        try:
            if sys.platform == 'darwin':
                p = subprocess.run('osascript -e \'get volume settings\'', capture_output=True, shell=True)
                if p.returncode != 0:
                    print('Error trying to get volume')
                    return None

                stdout = p.stdout.decode()
                lines = stdout.splitlines()
                first = lines[0]
                m = re.search(r'output volume:(\d+)', first)
                if m is None:
                    if self.DEBUG:
                        print('Error trying to get volume')
                    return None

                return int(m.group(1))
                
            else:
                #print(self.audio_controls)
                for option in self.audio_controls:
                    if str(self.persistent_data['audio_output']) == str(option["human_device_name"]):
                        if self.DEBUG:
                            print("  here is bingo, about to get current volume via linux amixer command")
                        
                        if option["control_name"] != None:
                            command = 'amixer -c ' + str(option["card_id"]) + ' -M -q sget \'' + str(option["control_name"])  + '\''
                            if self.DEBUG:
                                print(command)
                            #'amixer sget \'PCM\''
                    
                            try:
                                p = subprocess.run(command, capture_output=True, shell=True)
                                if p.returncode != 0:
                                    if self.DEBUG:
                                        print('Error trying to get volume from subproces')
                                    return None

                                stdout = p.stdout.decode()
                                if len(stdout) > 0:
                                    lines = stdout.splitlines()
                                    last = lines[-1]
                                    m = re.search(r'(\d+)%', last)
                                    if m is None:
                                        if self.DEBUG:
                                            print('Error trying to get volume (m is None)')
                                        return None

                                    return int(m.group(1))
                                
                            except Exception as ex:
                                print("error getting linux audio volume:" + str(ex))
                            
                        elif option["complex_control_id"] != None and option["complex_max"] != None:
                            try:
                                if self.DEBUG:
                                    print("simple control was None - this device does not have simple volume control option. But it does have a complex control.")
                            
                                command = 'amixer -c ' + str(option["card_id"]) + ' cget numid=' + str(option["complex_control_id"])
                                if self.DEBUG:
                                    print(command)
                                info_result = run_command(command) #amixer -c 1 cget numid=
                                if self.DEBUG:
                                    print(str(info_result))
                                
                                party = info_result.split(': values=')[1]
                                if self.DEBUG:
                                    print(str(party))
                                
                                
                                value = int(party.split(',')[0])
                                if self.DEBUG:
                                    print("complexly gotten volume: " + str(value))
                            
                                volume_percentage = round( value * ( 100 / int(option["complex_max"]) ) )
                                if self.DEBUG:
                                    print("complexly gotten volume percentage: " + str(volume_percentage))
                                
                                return volume_percentage

                            
                            except Exception as ex:
                                if self.DEBUG:
                                    print("Error trying to get complex volume: " + str(ex))
                            
                            #for part in info_result_parts:
                            #    if part.startswith('max='):
                            #        complex_max = int(part)
                            #        break
                            
                            
                            
                          #  numid=1,iface=PCM,name='Playback Channel Map'
                          #    ; type=INTEGER,access=r----R--,values=2,min=0,max=36,step=0
                          #    : values=0,0
                          #    | container
                          #      | chmap-fixed=FL,FR

                            
                        else:
                            if self.DEBUG:
                                print("Not enough info to get current volume")    
                            
                            
                            
                    #else:
                return None # if nothing worked, it will end up here.
                    
        except Exception as ex:
            print("Error trying to get volume: " + str(ex))



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
        #self.set_radio_state(0)
        self.running = False



    def remove_thing(self, device_id):
        try:
            self.set_radio_state(0)
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
            """
            self.properties["station"] = InternetRadioProperty(
                            self,
                            "station",
                            {
                                'title': "Station",
                                'type': 'string',
                                'enum': radio_station_names_list,
                            },
                            self.adapter.persistent_data['station'])
            """
            
            # this will also call handle_device_added
            self.update_stations_property(False)
            
            self.properties["power"] = InternetRadioProperty(
                            self,
                            "power",
                            {
                                '@type': 'OnOffProperty',
                                'title': "State",
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




            if sys.platform != 'darwin':
                if self.DEBUG:
                    print("adding audio output property with list: " + str(audio_output_list))
                self.properties["audio output"] = InternetRadioProperty(
                                self,
                                "audio output",
                                {
                                    'title': "Audio output",
                                    'type': 'string',
                                    'readOnly': False,
                                    'enum': audio_output_list,
                                },
                                self.adapter.persistent_data['audio_output'])




        except Exception as ex:
            if self.DEBUG:
                print("error adding properties: " + str(ex))

        if self.DEBUG:
            print("Internet Radio thing has been created.")



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
            human_device_name = human_device_name.replace("bcm2835 IEC958/HDMI1","Built-in video two")
            
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
        