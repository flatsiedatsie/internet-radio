"""Internet Radio API handler."""

import os
import re
import json
import time
from time import sleep
import socket
import requests
import subprocess


#from .util import valid_ip, arpa_detect_gateways

#from datetime import datetime,timedelta


try:
    from gateway_addon import APIHandler, APIResponse
    #print("succesfully loaded APIHandler and APIResponse from gateway_addon")
except:
    print("Import APIHandler and APIResponse from gateway_addon failed. Use at least WebThings Gateway version 0.10")
    sys.exit(1)


#from pyradios import RadioBrowser


class InternetRadioAPIHandler(APIHandler):
    """Internet Radio API handler."""

    def __init__(self, adapter, verbose=False):
        """Initialize the object."""
        #print("INSIDE API HANDLER INIT")
        
        self.adapter = adapter
        self.DEBUG = self.adapter.DEBUG


        # Intiate extension addon API handler
        try:
            manifest_fname = os.path.join(
                os.path.dirname(__file__),
                '..',
                'manifest.json'
            )

            with open(manifest_fname, 'rt') as f:
                manifest = json.load(f)

            APIHandler.__init__(self, manifest['id'])
            self.manager_proxy.add_api_handler(self)
            

            if self.DEBUG:
                print("self.manager_proxy = " + str(self.manager_proxy))
                print("Created new API HANDLER: " + str(manifest['id']))
        
        except Exception as e:
            print("Error: failed to init API handler: " + str(e))
        
        #self.rb = RadioBrowser()
                        

#
#  HANDLE REQUEST
#

    def handle_request(self, request):
        """
        Handle a new API request for this handler.

        request -- APIRequest object
        """
        #print("in handle_request")
        try:
        
            if request.method != 'POST':
                return APIResponse(status=404)
            
            if request.path == '/ajax':

                try:
                    #if self.DEBUG:
                    #    print("API handler is being called")
                    #    print("request.body: " + str(request.body))
                    
                    action = str(request.body['action']) 
                    
                    if action == 'init':
                        if self.DEBUG:
                            print("in init")
                        
                        return APIResponse(
                          status=200,
                          content_type='application/json',
                          content=json.dumps({'playing' : self.adapter.persistent_data['playing'], 'volume':self.adapter.persistent_data['volume'], 'debug': self.adapter.DEBUG, 'stations':self.adapter.persistent_data['stations'], 'station':self.adapter.persistent_data['station'], 'show_buttons_everywhere':self.adapter.show_buttons_everywhere}),
                        )
                        
                    elif action == 'poll':
                        return APIResponse(
                          status=200,
                          content_type='application/json',
                          content=json.dumps({'state' : 'ok', 'playing': self.adapter.persistent_data['playing'],'now_playing':self.adapter.now_playing, 'station': self.adapter.persistent_data['station'], 'volume':self.adapter.persistent_data['volume']}),
                        )
                        
                    elif action == 'add':
                        if self.DEBUG:
                            print("in add")
                        name = str(request.body['name']) 
                        stream_url = str(request.body['stream_url'])
                        #print('name:' + str(name))
                        #print('stream_url: ' + str(stream_url))
                        state = 'ok'
                        try:
                            if name != "" and stream_url.startswith('http'):
                                print("- add: valid inputs")
                                self.adapter.persistent_data['stations'].append({'name':name,'stream_url':stream_url})
                            
                                self.adapter.devices['internet-radio'].update_stations_property()
                            
                                self.adapter.save_persistent_data()
                                
                            else:
                                state = "Please provide a valid name"
                        except Exception as ex:
                            print("Error adding: " + str(ex))
                        
                        return APIResponse(
                          status=200,
                          content_type='application/json',
                          content=json.dumps({'state' : state}),
                        )
                        
                    elif action == 'volume_down':
                        if self.DEBUG:
                            print("in volume down")
                        state = False
                        try:
                            volume = self.adapter.persistent_data['volume'] - 5
                            if volume > 100:
                                volume = 100
                            #self.adapter.set_audio_volume(self.adapter.persistent_data['volume'])
                            
                            if self.DEBUG:
                                print("new volume: " + str(volume))
                            
                            if self.adapter.player != None:
                                if self.DEBUG:
                                    print("-")
                                self.adapter.set_audio_volume(volume)
                                #self.adapter.player.stdin.write(b'-')
                                #self.adapter.player.stdin.flush()
                                state = True
                            else:
                                if self.DEBUG:
                                    print("self.adapter.player was None")
                            
                        except Exception as ex:
                            if self.DEBUG:
                                print("API: error setting volume: " + str(ex))
                            
                            
                        return APIResponse(
                          status=200,
                          content_type='application/json',
                          content=json.dumps({'state' : state, 'volume': self.adapter.persistent_data['volume']}),
                        )
                        
                    elif action == 'volume_up':
                        if self.DEBUG:
                            print("in volume up")
                        state = False
                        try:
                            volume = self.adapter.persistent_data['volume'] + 5
                            if volume > 100:
                                volume = 100
                            
                            if self.DEBUG:
                                print("new volume: " + str(volume))
                                
                            if self.adapter.player != None:
                                if self.DEBUG:
                                    print("+")
                                self.adapter.set_audio_volume(volume)
                                state = True
                                #self.adapter.player.stdin.write(b'+')
                                #self.adapter.player.stdin.flush()
                            #self.adapter.set_audio_volume(self.adapter.persistent_data['volume'])
                            else:
                                if self.DEBUG:
                                    print("self.adapter.player was None")
                            
                        except Exception as ex:
                            if self.DEBUG:
                                print("API: error setting volume: " + str(ex))
                            
                        return APIResponse(
                          status=200,
                          content_type='application/json',
                          content=json.dumps({'state' : state, 'volume': self.adapter.persistent_data['volume']}),
                        )
                        
                    elif action == 'play':
                        if self.DEBUG:
                            print("in play")
                        stream_url = str(request.body['stream_url']) 
                        #url = str(request.body['url'])
                        state = 'ok'
                        self.adapter.poll_counter = 0
                        try:
                            self.adapter.set_radio_station(stream_url)     
                        except Exception as ex:
                            if self.DEBUG:
                                print("API: error setting station: " + str(ex))
                            state = "Error: could not change station"
                            
                        return APIResponse(
                          status=200,
                          content_type='application/json',
                          content=json.dumps({'state' : state}),
                        )
                        
                    elif action == 'toggle':
                        if self.DEBUG:
                            print("in toggle")
                        #url = str(request.body['url'])
                        #desired_state = bool(request.body['desired_state']) 
                        opposite = not self.adapter.persistent_data['playing']
                        try:
                            self.adapter.set_radio_state(opposite)        
                        except Exception as ex:
                            print("API: error setting station state: " + str(ex))
                            
                        return APIResponse(
                          status=200,
                          content_type='application/json',
                          content=json.dumps({'state' : 'ok', 'playing': opposite, 'volume': self.adapter.persistent_data['volume']}),
                        )
                        
                    elif action == 'delete':
                        if self.DEBUG:
                            print("in delete")
                        name = str(request.body['name'])
                        
                        state = 'ok'
                        try:
                            if len(self.adapter.persistent_data['stations']) > 1: #one station must remain
                                
                                # if we're deleting the station that is playing, play another station first
                                if self.adapter.persistent_data['station'] == name:
                                    self.adapter.persistent_data['station'] = self.adapter.persistent_data['stations'][0]['name']
                                    self.adapter.set_radio_station(self.adapter.persistent_data['station'])
                            
                                # remove it from the stations list
                                for i in range(len(self.adapter.persistent_data['stations'])):
                                    if self.adapter.persistent_data['stations'][i]['name'] == name:
                                        del self.adapter.persistent_data['stations'][i]
                                        break
                                        
                                # Update the device to have the correct enum
                                self.adapter.devices['internet-radio'].update_stations_property()
                                
                                self.adapter.save_persistent_data()
                            
                        except Exception as ex:
                            if self.DEBUG:
                                print("Error deleting station: " + str(ex))
                            state = 'Error: could not delete station'
                        
                        
                        return APIResponse(
                          status=200,
                          content_type='application/json',
                          content=json.dumps({'state' : state}),
                        )
                    
                    else:
                        return APIResponse(
                            status=500,
                            content_type='application/json',
                            content=json.dumps("API error"),
                        )
                        
                except Exception as ex:
                    if self.DEBUG:
                        print("Ajax issue: " + str(ex))
                    return APIResponse(
                        status=500,
                        content_type='application/json',
                        content=json.dumps("Error in API handler"),
                    )
                    
            else:
                if self.DEBUG:
                    print("invalid path: " + str(request.path))
                return APIResponse(status=404)
                
        except Exception as e:
            if self.DEBUG:
                print("Failed to handle UX extension API request: " + str(e))
            return APIResponse(
                status=500,
                content_type='application/json',
                content=json.dumps("General API Error"),
            )
        

