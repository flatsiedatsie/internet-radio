"""Internet radio adapter for Mozilla WebThings Gateway."""


import os
from os import path
import sys


sys.path.append(path.join(path.dirname(path.abspath(__file__)), 'lib'))

import json

import time

try:
    import vlc
    print("VLC was present")
except:
    print("VLC not installed yet.")
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
        print("initialising adapter from class")
        self.pairing = False
        self.DEBUG = True
        self.name = self.__class__.__name__
        Adapter.__init__(self, 'internet-radio-adapter', 'internet_radio', verbose=verbose)
        #print("Adapter ID = " + self.get_id())

        for path in _CONFIG_PATHS:
            if os.path.isdir(path):
                self.persistence_file_path = os.path.join(
                    path,
                    'internet-radio-persistence.json'
                )
                print("self.persistence_file_path is now: " + str(self.persistence_file_path))

        print("Current working directory: " + str(os.getcwd()))
        
        try:
            with open(self.persistence_file_path) as f:
                self.persistent_data = json.load(f)
                print("Persistence data was loaded succesfully")
        except:
            print("Could not load persistent data (if you just installed the add-on then this is normal)")
            self.persistent_data = {}

        self.addon_path =  os.path.join(os.path.expanduser('~'), '.mozilla-iot', 'addons', 'internet_radio')
        
        try:
            self.devices['internet_radio'].connected = False
            self.devices['internet_radio'].connected_notify(False)
            if self.install_vlc():
                self.devices['internet_radio'].connected = True
                self.devices['internet_radio'].connected_notify(True)
        except Exception as ex:
            print("Error installing VLC: " + str(ex))
            
        try:
            internet_radio_device = InternetRadioDevice(self)
            self.handle_device_added(internet_radio_device)
            print("internet_radio_device created")
        except Exception as ex:
            print("Could not create internet_radio_device: " + str(ex))
        
        # LOAD CONFIG
        
        self.radio_stations = None
        
        try:
            self.add_from_config()
        except Exception as ex:
            print("Error loading config: " + str(ex))
        
        
        
        try:
            
            self.vlc = vlc.Instance('--input-repeat=-1')

            #Define VLC player
            self.vlc_player=self.vlc.media_player_new()
            
        except Exception as ex:
            print("Error starting VLC object: " + str(ex))
            self.set_status_on_thing("Error starting VLC")
        
        # Should there be something blocking here?

        



    def add_from_config(self):
        """Attempt to add all configured devices."""
        try:
            database = Database('internet_radio')
            if not database.open():
                print("Could not open settings database")
                return
            
            config = database.load_config()
            database.close()
            
        except:
            print("Error! Failed to open settings database.")
        
        if not config:
            print("Error loading config from database")
            return
        
        print(str(config))

        try:
            store_updated_settings = False
            
            if 'Radio stations' in config:
                print("-Radio stations was in config")
                #new_url = str(config['Radio station'])
                print(str(new_url))
                if possible_url.startswith("http"):
                    print("-- Url started with http.")
                    self.new_stream_url = new_url

                elif possible_url == "Your new assistant has succesfully been installed":
                    print("Your new radio station was added")
                else:
                    print("Cannot use what you provided")
        except Exception as ex:
            print("Error loading radio stations: " + str(ex))
            
        
        try:    
            # Store the settings that were changed by the add-on.
            if store_updated_settings:
                print("Storing overridden settings")
                try:
                    database = Database('internet_radio')
                    if not database.open():
                        print("Could not open settings database")
                        #return
                    else:
                        database.save_config(config)
                        database.close()
                        print("Stored overridden preferences into the database")
                        
                except:
                    print("Error! Failed to store overridden settings in database.")
                
            if 'Debugging' in config:
                print("-Debugging was in config")
                self.DEBUG = bool(config['Debugging'])
                print("Debugging enabled")
            else:
                self.DEBUG = False
                
        except:
            print("Error loading settings")

            
    def set_status_on_thing(self,status_string):
        try:
            if self.devices['internet_radio'] != None:
                self.devices['internet_radio'].properties['status'].set_cached_value_and_notify( str(status_string) )
        except:
            print("Error setting status of internet radio device")



    def install_vlc(self):
        """Install VLC using a shell command"""
        try:
            done = os.path.isfile('/usr/share/vlc')
            if done:
                print("VLC is already installed")
                return True
            
            # Start installing VLC
            else:
                command = str(os.path.join(self.addon_path,"install_vlc.sh"))
                self.set_status_on_thing("Installing")
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
            #self.set_status_on_thing("Error during installation")
            
        return False


 

    def start_pairing(self, timeout):
        """
        Start the pairing process. This starts when the user presses the + button on the things page.
        
        timeout -- Timeout in seconds at which to quit pairing
        """
        #print()
        if self.DEBUG:
            print("PAIRING INITIATED")
        
        if self.pairing:
            print("-Already pairing")
            return
          
        self.pairing = True
        
        for item in self.action_times:
            print("action time: " + str(item))
        
        return
    
    
    
    def cancel_pairing(self):
        """Cancel the pairing process."""
        self.pairing = False



    def save_persistent_data(self):
        if self.DEBUG:
            print("Saving to persistence data store")
        try:
            if not os.path.isfile(self.persistence_file_path):
                open(self.persistence_file_path, 'a').close()
                print("Created an empty persistence file")

            with open(self.persistence_file_path) as f:
                print("saving: " + str(self.persistent_data))
                json.dump( self.persistent_data, open( self.persistence_file_path, 'w+' ) )
                print("Persistence data was stored succesfully")
                return True
            
        except Exception as ex:
            print("Error: could not store data in persistent store: " + str(ex) )
            return False

        
    def play_station(self, station_name):
        print("Play: station name: " + str(station_name))
        
        
    def play_stream(self, url):
        
        # update 'currently playing' status? Or is that the dropdown itself?
        
        #Define VLC media
        media=self.vlc.media_new(url)

        #Set player media
        self.vlc_player.set_media(media)

        #Play the media
        self.vlc_player.play()
        

    def set_radio_state(self,power):
        print("power:" + str(power))
        if power:
            self.vlc_player.play()
        else:
            self.vlc_player.stop()



from gateway_addon import Device, Property, Notifier, Outlet


#
# DEVICE
#

class InternetRadioDevice(Device):
    """Candle device type."""

    def __init__(self, adapter):
        """
        Initialize the object.
        adapter -- the Adapter managing this device
        """

        Device.__init__(self, adapter, 'internet_radio')
        
        self._id = 'internet_radio'
        self.id = 'internet_radio'
        self.adapter = adapter

        self.name = 'Internet radio'
        self.title = 'Internet radio'
        self.description = 'Listen to internet radio stations'
        self._type = ['MultiLevelSwitch']
        self.connected = False
        try:
            #volume_property = InternetRadioProperty(self,"volume",)
            self.properties["station"] = InternetRadioProperty(
                            self,
                            "station",
                            {
                                '@type': '',
                                'label': "Station",
                                'type': 'string',
                                'enum': [
                                  'Fip',
                                  'Soma',
                                  'string3',
                                  'string4',
                                ],
                            },
                            'Fip')

            #{
            #  name: 'stringEnumProperty',
            #  value: 'string1',
            #  metadata: {
            #    type: 'string',
            #  },
            #},
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

        except Exception as ex:
            print("error adding properties: " + str(ex))
        print("Internet Radio thing has been created.")
        #self.adapter.handle_device_added(self)



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
        print("property: set value: " + str(value))
        try:
            print("set_value called for " + str(self.title))
            if self.title == 'station':
                self.device.adapter.play_station(str(value))
                self.update(value)
                
            if self.title == 'power':
                self.device.adapter.set_radio_state(bool(value))
                self.update(value)
                
        except Exception as ex:
            print("set_value error: " + str(ex))

    def update(self, value):         
        print("property -> update")
        
        if value != self.value:
            self.value = value
            self.set_cached_value(value)
            self.device.notify_property_changed(self)