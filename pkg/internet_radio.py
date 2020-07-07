"""Internet radio adapter for Mozilla WebThings Gateway."""


from gateway_addon import Database, Adapter, Device, Property
from os import path
import json
import os
import re
import subprocess
import sys
import time
import threading
import requests  # noqa


sys.path.append(path.join(path.dirname(path.abspath(__file__)), 'lib'))



__location__ = os.path.realpath(
    os.path.join(os.getcwd(), os.path.dirname(__file__)))

_CONFIG_PATHS = [
    os.path.join(os.path.expanduser('~'), '.mozilla-iot', 'config'),
]

if 'MOZIOT_HOME' in os.environ:
    _CONFIG_PATHS.insert(0, os.path.join(os.environ['MOZIOT_HOME'], 'config'))


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
        self.DEBUG = True
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

        self.addon_path = os.path.join(os.path.expanduser('~'), '.mozilla-iot', 'addons', self.addon_name)
        #self.persistence_file_path = os.path.join(os.path.expanduser('~'), '.mozilla-iot', 'data', self.addon_name,'persistence.json')

        self.persistence_file_path = os.path.join(self.user_profile['dataDir'], self.addon_name, 'persistence.json')

        self.running = True

        self.audio_output_options = []

        # Get audio output options
        if sys.platform != 'darwin':
            self.audio_controls = get_audio_controls()
            print(self.audio_controls)
            # create list of human readable audio-only output options for Shairport-sync
            
            for option in self.audio_controls:
                self.audio_output_options.append( option['human_device_name'] )


        # LOAD CONFIG

        self.current_stream_url = None
        self.radio_stations = []
        self.radio_stations_names_list = []

        try:
            self.add_from_config()

        except Exception as ex:
            print("Error loading config: " + str(ex))


        # Create list of radio station names for the radio thing.
        for station in self.radio_stations:
            if self.DEBUG:
                print("Adding station: " + str(station))
                #print("adding station: " + str(station['name']))
            self.radio_stations_names_list.append(str(station['name']))


        # Get persistent data
        try:
            with open(self.persistence_file_path) as f:
                self.persistent_data = json.load(f)
                if self.DEBUG:
                    print("Persistence data was loaded succesfully.")
        except:
            print("Could not load persistent data (if you just installed the add-on then this is normal)")
            self.persistent_data = {'power':False,'station':self.radio_stations_names_list[0],'volume':100, 'audio_output': str(self.audio_controls[0]['human_device_name']) }


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
                self.set_radio_station(self.persistent_data['station'])
        except Exception as ex:
            print("couldn't set the radio station name to what it was before: " + str(ex))


        # Restore power
        try:
            self.set_radio_state(bool(self.persistent_data['power']))
        except Exception as ex:
            print("Could not restore radio station: " + str(ex))


        # Start the internal clock, used to sync the volume.
        #print("Starting the internal clock")
        #try:
        #    t = threading.Thread(target=self.clock)
        #    t.daemon = True
        #    t.start()
        #except:
        #    print("Error starting the clock thread")
        




    def add_from_config(self):
        """Attempt to add all configured devices."""
        try:
            database = Database(self.addon_name)
            if not database.open():
                print("Could not open settings database")
                return

            config = database.load_config()
            database.close()

        except:
            print("Error! Failed to open settings database.")

        if not config:
            return

        if 'Debugging' in config:
            print("-Debugging was in config")
            self.DEBUG = bool(config['Debugging'])
            if self.DEBUG:
                print("Debugging enabled")

        if self.DEBUG:
            print(str(config))

        try:
            if 'Radio stations' in config:
                self.radio_stations = config['Radio stations']
                if self.DEBUG:
                    print("self.radio_stations was in config: " + str(self.radio_stations))

        except Exception as ex:
            print("Error loading radio stations: " + str(ex))




#
# CLOCK
#

    def clock(self):
        """ Runs every second and handles the various timers """

        while self.running:
            
            # If the audio output volume was changed, but not by this add-on
            try:
                current_volume = self.get_audio_volume()
                if current_volume != None:
                    if self.persistent_data['volume'] != current_volume:
                        self.persistent_data['volume'] = current_volume
                        self.save_persistent_data()
                        self.set_volume_on_thing(current_volume)

            except Exception as ex:
                if self.DEBUG:
                    print("Error getting current audio volume: " + str(ex))
            
            time.sleep(2)




#
# MAIN SETTING OF THE RADIO STATES
#

    def set_radio_station(self, station_name):
        if self.DEBUG:
            print("Setting radio station to: " + str(station_name))
        try:
            url = ""
            for station in self.radio_stations:
                if station['name'] == station_name:
                    #print("station name match")
                    url = station['stream_url']
                    if str(station_name) != str(self.persistent_data['station']):
                        self.persistent_data['station'] = str(station_name)
                        self.save_persistent_data()
                    if self.DEBUG:
                        print("setting station name on thing")
                    self.set_station_on_thing(str(station['name']))

            if url.startswith('http') or url.startswith('rtsp'):
                print("URL starts with http or rtsp")
                if url.endswith('.m3u') or url.endswith('.pls'):
                    if self.DEBUG:
                        print("URL ended with .m3u or .pls (is a playlist)")
                    url = self.scrape_url_from_playlist(url)
                    if self.DEBUG:
                        print("Extracted URL = " + str(url))

                self.current_stream_url = url
                
                # Finally, if the station is changed, also turn on the radio
                self.set_radio_state(True)
                
            else:
                self.set_status_on_thing("Not a valid URL")
        except Exception as ex:
            print("Error playing station: " + str(ex))




    def set_radio_state(self,power):
        if self.DEBUG:
            print("Setting radio power to " + str(power))
        try:
            if bool(power) != bool(self.persistent_data['power']):
                self.persistent_data['power'] = bool(power)
                self.save_persistent_data()

            if power:
                self.set_status_on_thing("Playing")
                if self.player != None:
                    self.player.terminate()
                    
                    
                    
                environment = {}#os.environ.copy()
                
                
                if sys.platform != 'darwin':
                    for option in self.audio_controls:
                        if option['human_device_name'] == str(self.persistent_data['audio_output']):
                            environment["ALSA_CARD"] = str(option['simple_card_name'])
                            print("environment = " + str(environment))
                            
                #my_command = "ffplay -nodisp -vn -infbuf -autoexit" + str(self.current_stream_url) + " -volume " + str(self.persistent_data['volume'])
                my_command = ("ffplay", "-nodisp", "-vn", "-infbuf","-autoexit", str(self.current_stream_url),"-volume",str(self.persistent_data['volume']))

                self.player = subprocess.Popen(my_command, 
                                env=environment,
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
                   
            else:
                self.set_status_on_thing("Stopped")
                if self.player != None:
                    self.player.terminate()
                else:
                    if self.DEBUG:
                        print("Could not stop the player because it wasn't running.")

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
        self.set_radio_state(True)



        # Not all USB devices can have their volume set via a command, so a solution here is to use the volume control on ffplay itself.
        # The downside is that this volume will be relative to the current main device volume. 
        # If the main volume is at 50%, and the radio volume is at 50%, then the actual volume will be 25%.
        if 1 is 0:
            try:
                if sys.platform == 'darwin':
                    command = 'osascript -e \'set volume output volume {}\''.format(volume)
                    os.system(command)
                
                    if self.DEBUG:
                        print("New macOS volume has been set")
                
                else:
                    for option in self.audio_controls:
                        if str(self.persistent_data['audio_output']) == str(option["human_device_name"]):
                            print("setting linux volume")
                        
                            # If there is a 'simple control', use that.
                            if option["control_name"] != None:
                            
                                print("control_name was set: " + str(option["control_name"]))
                                os.system('amixer sset ' + option["control_name"] + ' unmute')
                                command = 'amixer -c ' + str(option["card_id"]) + ' -M -q sset \'' + str(option["control_name"])  + '\' {}%'.format(volume)
                                print(command)
                                os.system(command)
                            
                            
                            # Otherwise, try using the 'complex control' instead
                            elif option["control_name"] == None and option["complex_control_id"] != None and option["complex_max"] != None and option["complex_count"] != None:
                                #os.system('amixer sset ' + option["control_name"] + ' unmute')
                            
                                new_volume = int(( int(option["complex_max"]) / 100 ) * int(volume) )
                            
                                command = 'sudo amixer -c ' + str(option["card_id"]) + ' cset numid=' + str(option["complex_control_id"]) + ' ' + str(new_volume)
                            
                                if int(option["complex_count"]) == 2:
                                    #command = 'amixer -c ' + str(option["card_id"]) + ' -M -q sset \'' + str(option["control_name"])  + '\' {}%'.format(volume)
                                    command = command + ',' + str(new_volume)
                            
                                print(command)
                                os.system(command)
                            
                                #amixer -c 1 cset numid=6 37,37
                
                            if self.DEBUG:
                                print("New linux audio volume has been set")
                        
                    # Pi 4 - headphone
                    #command = 'amixer -c 0 -M -q sset \'PCM\' {}%'.format(volume)
                    #os.system(command)
                
                    # Pi 3 - headphone
                    #command = 'amixer -c 1 -M -q sset \'Headphone\' {}%'.format(volume)
                    #os.system(command)
                
                    # Pi 3 - just in case there is a speaker in the display
                    #command = 'amixer -c 0 -M -q sset \'HDMI\' {}%'.format(volume)
                    #os.system(command)
                
                    # ReSpeaker GPIO board headphone
                    #command = 'amixer -c 2 -M -q sset \'Headphone\' {}%'.format(volume)
                    #os.system(command)
                
                
                        
            except Exception as ex:
                print("Error trying to set volume: " + str(ex))




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
                    print('Error trying to get volume')
                    return None

                return int(m.group(1))
                
            else:
                #print(self.audio_controls)
                for option in self.audio_controls:
                    if str(self.persistent_data['audio_output']) == str(option["human_device_name"]):
                        print("  here is bingo, about to get current volume via linux amixer command")
                        
                        if option["control_name"] != None:
                            command = 'amixer -c ' + str(option["card_id"]) + ' -M -q sget \'' + str(option["control_name"])  + '\''
                            print(command)
                            #'amixer sget \'PCM\''
                    
                            try:
                                p = subprocess.run(command, capture_output=True, shell=True)
                                if p.returncode != 0:
                                    print('Error trying to get volume')
                                    return None

                                stdout = p.stdout.decode()
                                if len(stdout) > 0:
                                    lines = stdout.splitlines()
                                    last = lines[-1]
                                    m = re.search(r'(\d+)%', last)
                                    if m is None:
                                        print('Error trying to get volume (m is None)')
                                        return None

                                    return int(m.group(1))
                                
                            except Exception as ex:
                                print("error getting linux audio volume:" + str(ex))
                            
                        elif option["complex_control_id"] != None and option["complex_max"] != None:
                            try:
                                print("simple control was None - this device does not have simple volume control option. But it does have a complex control.")
                            
                                command = 'amixer -c ' + str(option["card_id"]) + ' cget numid=' + str(option["complex_control_id"])
                                print(command)
                                info_result = run_command(command) #amixer -c 1 cget numid=
                                print(str(info_result))
                                
                                party = info_result.split(': values=')[1]
                                print(str(party))
                                
                                
                                value = int(party.split(',')[0])
                                print("complexly gotten volume: " + str(value))
                            
                                volume_percentage = round( value * ( 100 / int(option["complex_max"]) ) )
                                print("complexly gotten volume percentage: " + str(volume_percentage))
                                
                                return volume_percentage

                            
                            except Exception as ex:
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
            print("Error setting status of internet radio device")



    def set_state_on_thing(self, power):
        if self.DEBUG:
            print("new state on thing: " + str(power))
        try:
            if self.devices['internet-radio'] != None:
                self.devices['internet-radio'].properties['power'].update( bool(power) )
        except Exception as ex:
            print("Error setting power state of internet radio device:" + str(ex))



    def set_station_on_thing(self, station):
        if self.DEBUG:
            print("new station on thing: " + str(station))
        try:
            if self.devices['internet-radio'] != None:
                self.devices['internet-radio'].properties['station'].update( str(station) )
        except Exception as ex:
            print("Error setting station of internet radio device:" + str(ex))



    def set_volume_on_thing(self, volume):
        if self.DEBUG:
            print("new volume on thing: " + str(volume))
        try:
            if self.devices['internet-radio'] != None:
                self.devices['internet-radio'].properties['volume'].update( int(volume) )
        except Exception as ex:
            print("Error setting volume of internet radio device:" + str(ex))



    # Only called on non-darwin devices
    def set_audio_output(self, selection):
        if self.DEBUG:
            print("Setting audio output selection to: " + str(selection))
            
        # Get the latest audio controls
        self.audio_controls = get_audio_controls()
        print(self.audio_controls)
        
        try:        
            for option in self.audio_controls:
                if str(option['human_device_name']) == str(selection):
                    print("CHANGING INTERNET RADIO AUDIO OUTPUT")
                    # Set selection in persistence data
                    self.persistent_data['audio_output'] = str(selection)
                    print("persistent_data is now: " + str(self.persistent_data))
                    self.save_persistent_data()
                    
                    if self.DEBUG:
                        print("new selection on thing: " + str(selection))
                    try:
                        print("self.devices = " + str(self.devices))
                        if self.devices['internet-radio'] != None:
                            self.devices['internet-radio'].properties['audio output'].update( str(selection) )
                    except Exception as ex:
                        print("Error setting new audio output selection:" + str(ex))
        
                    if self.persistent_data['power']:
                        print("restarting radio with new audio output")
                        self.set_radio_state(True)
                    break
            
        except Exception as ex:
            print("Error in set_audio_output: " + str(ex))
                







    def scrape_url_from_playlist(self, url):
        response = requests.get(url)
        data = response.text

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
        return url



    def unload(self):
        if self.DEBUG:
            print("Shutting down Internet Radio.")
        self.set_status_on_thing("Bye")
        self.set_radio_state(0)
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
                #if self.DEBUG:
                #    print("saving: " + str(self.persistent_data))
                json.dump( self.persistent_data, open( self.persistence_file_path, 'w+' ) )
                return True
            #self.previous_persistent_data = self.persistent_data.copy()

        except Exception as ex:
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

        self.name = 'Radio'
        self.title = 'Radio'
        self.description = 'Listen to internet radio stations'
        self._type = ['MultiLevelSwitch']
        #self.connected = False

        self.radio_station_names_list = radio_station_names_list

        try:
            self.properties["station"] = InternetRadioProperty(
                            self,
                            "station",
                            {
                                'label': "Station",
                                'type': 'string',
                                'enum': radio_station_names_list,
                            },
                            self.adapter.persistent_data['station'])

            self.properties["status"] = InternetRadioProperty(
                            self,
                            "status",
                            {
                                'label': "Status",
                                'type': 'string',
                                'readOnly': True
                            },
                            "Hello")

            self.properties["power"] = InternetRadioProperty(
                            self,
                            "power",
                            {
                                '@type': 'OnOffProperty',
                                'label': "Power",
                                'type': 'boolean'
                            },
                            self.adapter.persistent_data['power'])

            self.properties["volume"] = InternetRadioProperty(
                            self,
                            "volume",
                            {
                                '@type': 'LevelProperty',
                                'label': "Volume",
                                'type': 'integer',
                                'minimum': 0,
                                'maximum': 100,
                                'unit': 'percent'
                            },
                            self.adapter.persistent_data['volume'])

            if sys.platform != 'darwin':
                print("adding audio output property with list: " + str(audio_output_list))
                self.properties["audio output"] = InternetRadioProperty(
                                self,
                                "audio output",
                                {
                                    'label': "Audio output",
                                    'type': 'string',
                                    'enum': audio_output_list,
                                },
                                self.adapter.persistent_data['audio_output'])


        except Exception as ex:
            print("error adding properties: " + str(ex))

        print("Internet Radio thing has been created.")



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



    def set_value(self, value):
        #print("property: set_value called for " + str(self.title))
        #print("property: set value to: " + str(value))
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
            print(str(lines))
            print("amixer lines array length: " + str(len(lines)))
            if len(lines) > 0:
                for line in lines:
                    if "'" in line:
                        #print("line = " + line)
                        control_name = re.findall(r"'([^']+)'", line)[0]
                        #print("control name = " + control_name)
                        if control_name is not 'mic':
                            break
                        else:
                            continue # in case the first control is 'mic', ignore it.
                    else:
                        control_name = None
            
            # if there is no 'simple control', then a backup method is to get the normal control options.  
            else:
                print("get audio controls: no simple control found, getting complex one instead")
                #line_counter = 0
                amixer_result = run_command('amixer -c ' + str(card_id) + ' controls')
                lines = amixer_result.splitlines()
                if len(lines) > 0:
                    for line in lines:
                        #line_counter += 1
                        
                        line = line.lower()
                        print("line.lower = " + line)
                        if "playback" in line:
                            print("playback spotted")
                            
                            numid_part = line.split(',')[0]
                            
                            if numid_part.startswith("numid="):
                                numid_part = numid_part[6:]
                                print("numid_part = " + str(numid_part))
                            
                                #complex_max = 36
                                complex_count = 1 # mono
                                complex_control_id = int(numid_part)
                                print("complex_control_id = " + str(complex_control_id))
                            
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
                            
                            
                
            
                
            if control_name is 'mic':
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
        print(str(target) + " stopped")
        return True
    except:
        print("Error stopping " + str(target))
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
        