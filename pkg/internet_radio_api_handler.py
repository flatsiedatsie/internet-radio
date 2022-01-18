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


        self.poll_counter = 0
            
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
                        return APIResponse(
                          status=200,
                          content_type='application/json',
                          content=json.dumps({'playing' : self.adapter.playing, 'debug': self.adapter.DEBUG, 'stations':self.adapter.persistent_data['stations'], 'station':self.adapter.persistent_data['station']}),
                        )
                        
                    elif action == 'poll':
                        try:
                            if self.DEBUG:
                                print(str(self.poll_counter))
                            if self.poll_counter == 0:
                                self.adapter.now_playing = self.adapter.get_artist()
                        except Exception as ex:
                            print("error updating now_playing: " + str(ex))
                            
                        self.poll_counter += 1
                        if self.poll_counter > 20:
                            self.poll_counter = 0
                            
                        return APIResponse(
                          status=200,
                          content_type='application/json',
                          content=json.dumps({'state' : 'ok', 'playing': self.adapter.playing,'now_playing':self.adapter.now_playing}),
                        )
                        
                    elif action == 'add':
                        #print("in add")
                        name = str(request.body['name']) 
                        stream_url = str(request.body['stream_url'])
                        #print('name:' + str(name))
                        #print('stream_url: ' + str(stream_url))
                        state = 'ok';
                        if name != "" and stream_url.startswith('http'):
                            self.adapter.persistent_data['stations'].append({'name':name,'stream_url':stream_url})
                        else:
                            state = "Please provide a valid name"
                        
                        return APIResponse(
                          status=200,
                          content_type='application/json',
                          content=json.dumps({'state' : state}),
                        )
                        
                    elif action == 'play':
                        #print("in play")
                        stream_url = str(request.body['stream_url']) 
                        #url = str(request.body['url'])
                        state = 'ok'
                        self.poll_counter = 0
                        try:
                            self.adapter.set_radio_station(stream_url)     
                        except Exception as ex:
                            if self.DEBUG:
                                print("API: error setting station: " + str(ex))
                            state = "Error: could not change station";
                            
                        return APIResponse(
                          status=200,
                          content_type='application/json',
                          content=json.dumps({'state' : state}),
                        )
                        
                    elif action == 'toggle':
                        #print("in toggle")
                        #url = str(request.body['url'])
                        #desired_state = bool(request.body['desired_state']) 
                        opposite = not self.adapter.playing;
                        try:
                            self.adapter.set_radio_state(opposite)        
                        except Exception as ex:
                            print("API: error setting station state: " + str(ex))
                            
                        return APIResponse(
                          status=200,
                          content_type='application/json',
                          content=json.dumps({'state' : 'ok', 'playing': opposite}),
                        )
                        
                    elif action == 'delete':
                        #print("in quick delete")
                        name = str(request.body['name'])
                        
                        state = 'ok'
                        try:
                            for i in range(len(self.persistent_data['stations'])):
                                if self.persistent_data['stations'][i]['name'] == name:
                                    del self.persistent_data['stations'][i]
                                    break
                                    
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
        

