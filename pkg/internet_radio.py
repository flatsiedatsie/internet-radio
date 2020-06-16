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
        self.persistence_file_path = os.path.join(os.path.expanduser('~'), '.mozilla-iot', 'data', self.addon_name,'persistence.json')

        self.running = True




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


        try:
            with open(self.persistence_file_path) as f:
                self.persistent_data = json.load(f)
                if self.DEBUG:
                    print("Persistence data was loaded succesfully.")
        except:
            print("Could not load persistent data (if you just installed the add-on then this is normal)")
            self.persistent_data = {'power':False,'station':self.radio_stations_names_list[0],'volume':100}


        try:
            internet_radio_device = InternetRadioDevice(self, self.radio_stations_names_list)
            self.handle_device_added(internet_radio_device)
            if self.DEBUG:
                print("internet_radio_device created")
            self.devices['internet-radio'].connected = True
            self.devices['internet-radio'].connected_notify(True)

        except Exception as ex:
            print("Could not create internet_radio_device: " + str(ex))


        self.player = None

        # Restore volume
        try:
            self.set_radio_volume(self.persistent_data['volume'])
        except Exception as ex:
            print("Could not restore radio station: " + str(ex))

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
        print("Starting the internal clock")
        try:
            
            t = threading.Thread(target=self.clock)
            t.daemon = True
            t.start()
        except:
            print("Error starting the clock thread")
        




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
            current_volume = self.get_radio_volume()
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
                my_command = ("ffplay", "-nodisp", "-autoexit", str(self.current_stream_url))
                self.player = subprocess.Popen(my_command,
                                 stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
            else:
                self.set_status_on_thing("Stopped")
                if self.player != None:
                    self.player.terminate()
                else:
                    if self.DEBUG:
                        print("Could not stop the player, it wasn't loaded.")

            self.set_state_on_thing(bool(power))

        except Exception as ex:
            print("Error setting radio state: " + str(ex))



    def set_radio_volume(self,volume):
        if self.DEBUG:
            print("Setting radio volume to " + str(volume))
        if int(volume) != self.persistent_data['volume']:
            self.persistent_data['volume'] = int(volume)
            self.save_persistent_data()

        try:
            if sys.platform == 'darwin':
                command = \
                    'osascript -e \'set volume output volume {}\''.format(
                        volume
                    )
            else:
                command = 'amixer -q sset \'PCM\' {}%'.format(volume)

            if self.DEBUG:
                print("Command to change volume: " + str(command))

            os.system(command)

            if self.DEBUG:
                print("New volume has been set")
        except Exception as ex:
            print("Error trying to set volume: " + str(ex))

        self.set_volume_on_thing(volume)


    def get_radio_volume(self):
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
                p = subprocess.run('amixer sget \'PCM\'', capture_output=True, shell=True)
                if p.returncode != 0:
                    print('Error trying to get volume')
                    return None

                stdout = p.stdout.decode()
                lines = stdout.splitlines()
                last = lines[-1]
                m = re.search(r'(\d+)%', last)
                if m is None:
                    print('Error trying to get volume')
                    return None

                return int(m.group(1))
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
    """Candle device type."""

    def __init__(self, adapter, radio_station_names_list):
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
                self.device.adapter.set_radio_volume(int(value))
                #self.update(value)

        except Exception as ex:
            print("set_value error: " + str(ex))



    def update(self, value):
        #print("property -> update")
        if value != self.value:
            self.value = value
            self.set_cached_value(value)
            self.device.notify_property_changed(self)
