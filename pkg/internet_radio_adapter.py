"""Internet radio adapter for Mozilla WebThings Gateway."""


import os
from os import path
import sys

import subprocess

sys.path.append(path.join(path.dirname(path.abspath(__file__)), 'lib'))

import json

import time

try:
    import vlc
    if self.DEBUG:
        print("VLC was present")
except:
    print("python-vlc dependency not installed yet. Try 'pip3 install python-vlc'")

    #print('Python:', sys.version)
#print('requests:', requests.__version__)

from gateway_addon import Database, Adapter, Device, Property



__location__ = os.path.realpath(
    os.path.join(os.getcwd(), os.path.dirname(__file__)))

_CONFIG_PATHS = [
    os.path.join(os.path.expanduser('~'), '.mozilla-iot', 'config'),
]

if 'MOZIOT_HOME' in os.environ:
    _CONFIG_PATHS.insert(0, os.path.join(os.environ['MOZIOT_HOME'], 'config'))




class InternetRadioAdapter(Adapter):
    """Adapter for Internet Radio"""

    def __init__(self, verbose=True):
        """
        Initialize the object.
        
        verbose -- whether or not to enable verbose logging
        """
        
        #print("initialising adapter from class")
        self.pairing = False
        self.DEBUG = True
        self.name = self.__class__.__name__
        Adapter.__init__(self, 'internet-radio-adapter', 'internet-radio', verbose=verbose)

        self.addon_path =  os.path.join(os.path.expanduser('~'), '.mozilla-iot', 'addons', 'internet-radio')

        
        # LOAD CONFIG
        
        self.radio_stations = []
        self.radio_stations_names_list = []
        
        try:
            self.add_from_config()
        
        except Exception as ex:
            print("Error loading config: " + str(ex))
        
        # Create list of radio station names for the radio thing.
        for station in self.radio_stations:
            if self.DEBUG:
                print("station: " + str(station))
            print("adding station: " + str(station['name']))
            self.radio_stations_names_list.append(str(station['name']))

        
        try:
            internet_radio_device = InternetRadioDevice(self, self.radio_stations_names_list)
            self.handle_device_added(internet_radio_device)
            print("internet_radio_device created")
            self.devices['internet-radio'].connected = False
            self.devices['internet-radio'].connected_notify(False)
        
        except Exception as ex:
            print("Could not create internet_radio_device: " + str(ex))
        

        # Check if VLC is installed
        try:
            if self.install_vlc():
                self.devices['internet-radio'].connected = True
                self.devices['internet-radio'].connected_notify(True)
        
        except Exception as ex:
            print("Error installing VLC: " + str(ex))
            

        # Create VLC instance
        try:
            self.vlc = vlc.Instance('--input-repeat=-1')
            self.vlc_player=self.vlc.media_player_new()
            
        except Exception as ex:
            print("Error starting VLC object: " + str(ex))
            self.set_status_on_thing("Error starting VLC")

        # Load a default radio station
        try:
            url = ""
            if len(self.radio_stations) > 0:
                url = self.radio_stations[0]['stream_url']
                if url.startswith('http'):
                    media=self.vlc.media_new(url)
                    self.vlc_player.set_media(media)
        except Exception as ex:
            print("Error pre-loading VLC with default radio station:" + str(ex))
        
        # Start turned off
        self.set_state_on_thing(False)



    def add_from_config(self):
        """Attempt to add all configured devices."""
        try:
            database = Database('internet-radio')
            if not database.open():
                print("Could not open settings database")
                return
            
            config = database.load_config()
            database.close()
            
        except:
            print("Error! Failed to open settings database.")
        
        if not config:
            return
        
        if self.DEBUG:
            print(str(config))

        try:
            store_updated_settings = False
            
            if 'Radio stations' in config:
                print("-Radio stations was in config")
                self.radio_stations = config['Radio stations']
                if self.DEBUG:
                    print("self.radio_stations in config: " + str(self.radio_stations))
                
        except Exception as ex:
            print("Error loading radio stations: " + str(ex))



    def set_status_on_thing(self, status_string):
        print("new status on thing: " + str(status_string))
        try:
            if self.devices['internet-radio'] != None:
                self.devices['internet-radio'].properties['status'].set_cached_value_and_notify( str(status_string) )
        except:
            print("Error setting status of internet radio device")
            
            
            
    def set_state_on_thing(self, power):
        print("new state on thing: " + str(power))
        try:
            if self.devices['internet-radio'] != None:
                self.devices['internet-radio'].properties['power'].set_cached_value_and_notify( bool(power) )
        except:
            print("Error setting power state of internet radio device")

            
            

    def install_vlc(self):
        """Install VLC using a shell command"""
        try:
            done = os.path.isdir('/usr/share/vlc')
            if done:
                if self.DEBUG:
                    print("VLC is already installed")
                return True
            
            # Start installing VLC
            else:
                print("Will try to instal VLC player.")
                command = str(os.path.join(self.addon_path,"install_vlc.sh"))
                self.set_status_on_thing("Installing")
                if self.DEBUG:
                    print("VLC install command: " + str(command))
                for line in run_command(command):
                    print(str(line))
                    if line.startswith('Command success'):
                        print("VLC installation was succesful")
                        self.set_status_on_thing("Installed")
                        return True
                    elif line.startswith('Command failed'):
                        print("VLC installation failed")
                        self.set_status_on_thing("Error installing")
                        
        except Exception as ex:
            print("Error installing VLC: " + str(ex))
            self.set_status_on_thing("Error during installation")
            
        return False


 

    def start_pairing(self, timeout):
        """
        Start the pairing process. This starts when the user presses the + button on the things page.
        
        timeout -- Timeout in seconds at which to quit pairing
        """
        if self.DEBUG:
            print("PAIRING INITIATED")
        
        if self.pairing:
            #print("-Already pairing")
            return
          
        self.pairing = True
        return
    
    
    
    def cancel_pairing(self):
        """Cancel the pairing process."""
        self.pairing = False



    def unload(self):
        print("Shutting down Internet Radio. Adios!")
        self.set_status_on_thing("Disabled")
        self.set_radio_state(0)



    def remove_thing(self, device_id):
        try:
            self.set_radio_state(0)
            obj = self.get_device(device_id)        
            self.handle_device_removed(obj)                     # Remove from device dictionary
            if self.DEBUG:
                print("User removed Internet Radio device")
        except:
            print("Could not remove things from devices")
        
        



    def play_station(self, station_name):
        if self.DEBUG:
            print("Play: station name: " + str(station_name))
        try:
            url = ""
            for station in self.radio_stations:
                if station['name'] == station_name:
                    url = station['stream_url']
            if url.startswith('http'):
                media=self.vlc.media_new(url)
                self.vlc_player.set_media(media)
                self.vlc_player.play()
                self.set_state_on_thing(True)
            else:
                self.set_status_on_thing("Not a valid URL")
        except Exception as ex:
            print("Error playing station: " + str(ex))



    def set_radio_state(self,power):
        if power:
            self.set_status_on_thing("Playing")
            self.vlc_player.play()
        else:
            self.set_status_on_thing("Stopped")
            self.vlc_player.stop()

            
    def set_radio_volume(self,volume):
        try:
            self.vlc_player.audio_set_volume(volume)
        except:
            print("Could not change VLC player volume")


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

        self.name = 'Internet radio'
        self.title = 'Internet radio'
        self.description = 'Listen to internet radio stations'
        self._type = ['MultiLevelSwitch']
        self.connected = False

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
                            'Fip')

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
                                '@type':'OnOffProperty',
                                'label': "Power",
                                'type': 'boolean'
                            },
                            True)
            
            self.properties["volume"] = InternetRadioProperty(
                            self,
                            "volume",
                            {
                                '@type': 'LevelProperty',
                                'label': "Volume",
                                'type': 'integer',
                                'minimum': 0,
                                'maximum': 100,
                                'unit':'percent'
                            },
                            100)
            
        except Exception as ex:
            print("error adding properties: " + str(ex))
            
        print("Internet Radio thing has been created.")



#
# PROPERTY
#

class InternetRadioProperty(Property):

    def __init__(self, device, name, description, value):
        #print("")
        #print("Init of property")
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
                self.device.adapter.play_station(str(value))
                self.update(value)
                
            if self.title == 'power':
                self.device.adapter.set_radio_state(bool(value))
                self.update(value)

            if self.title == 'volume':
                self.device.adapter.set_radio_volume(int(value))
                self.update(value)

        except Exception as ex:
            print("set_value error: " + str(ex))



    def update(self, value):
        #print("property -> update")
        if value != self.value:
            self.value = value
            self.set_cached_value(value)
            self.device.notify_property_changed(self)


            
#
# UTILS
#

def run_command(command):
    try:
        p = subprocess.Popen(command,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            shell=True)
        # Read stdout from subprocess until the buffer is empty !
        for bline in iter(p.stdout.readline, b''):
            line = bline.decode('ASCII') #decodedLine = lines.decode('ISO-8859-1')
            if line: # Don't print blank lines
                yield line
        # This ensures the process has completed, AND sets the 'returncode' attr
        while p.poll() is None:                                                                                                                                        
            sleep(.1) #Don't waste CPU-cycles
        # Empty STDERR buffer
        err = p.stderr.read()
        if p.returncode == 0:
            yield("Command success")
        else:
            # The run_command() function is responsible for logging STDERR 
            #print("len(err) = " + str(len(err)))
            if len(err) > 1:
                yield("Error: " + str(err.decode('utf-8')))
            yield("Command failed")
            #return False
    except Exception as ex:
        print("Error running shell command: " + str(ex))   
