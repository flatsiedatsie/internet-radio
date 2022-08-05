(function() {
	class InternetRadio extends window.Extension {
	    constructor() {
	      	super('internet-radio');
			//console.log("Adding internet-radio addon to menu");
      		
			this.addMenuEntry('Internet radio');
            
            //var getCountryNames = new Intl.DisplayNames(['en'], {type: 'region'});
            //console.log(getCountryNames);
            //console.log(getCountryNames.of('AL'));  // "Albania"
            
            this.debug = false;
            
            this.interval = null;
			this.attempts = 0;

	      	this.content = '';
			this.item_elements = []; //['thing1','property1'];
			this.all_things;
			this.items_list = [];
			this.current_time = 0;
            this.show_buttons_everywhere = false;
            
            this.previous_volume = 0;
            this.volume_indicator_countdown = 0;
            
            this.stations = [];
            this.station = ""; // name of station that is currently playing (if the user has named the stream)
            
            this.searching = false;
            this.entered_search_page = false;
            this.radio_browser_server = "";
            this.get_more_search_results = true; // if the searh should give more than 20 results
            
            
            // Debug
            /*
            if(!this.entered_search_page){
                //console.log("getting server address of radio browser server");
                this.entered_search_page = true;
                this.get_radiobrowser_base_url_random()
                .then((url) =>{
                    this.radio_browser_server = url;
                    //console.log("url: " + url);
                });
            }*/
            
            
			fetch(`/extensions/${this.id}/views/content.html`)
	        .then((res) => res.text())
	        .then((text) => {
	         	this.content = text;
	  		 	if( document.location.href.endsWith("extensions/internet-radio") ){
					//console.log(document.location.href);
	  		  		this.show();
	  		  	}
	        })
	        .catch((e) => console.error('Failed to fetch content:', e));
            
            this.get_init_data(false); // do not generate the radio stations list yet
            
	    }



		
		hide() {
			//console.log("internet-radio hide called");
			try{
                this.stop_audio_in_browser();
                //console.log("audio player stopped");
                if(this.show_buttons_everywhere == false){
                    clearInterval(this.interval);
                    this.interval = null;
                }
				
				
			}
			catch(e){
				//console.log("internet radio: no interval to clear? " + e);
			}    
		}
        
        
        

	    show() {
			//console.log("internet-radio show called");
			//console.log("this.content:");
			//console.log(this.content);
			try{
				clearInterval(this.interval);
			}
			catch(e){
				//console.log("no interval to clear?: " + e);
			}
            
            
			const main_view = document.getElementById('extension-internet-radio-view');
			
			if(this.content == ''){
				return;
			}
			else{
				main_view.innerHTML = this.content;
			}
			
			main_view.audio_player = new Audio();
			//console.log("audio player: ", document.getElementById('extension-internet-radio-view').audio_player);

			const list = document.getElementById('extension-internet-radio-list');
		
			const pre = document.getElementById('extension-internet-radio-response-data');
            
            // Copy to clipboard
			const now_playing_element = document.getElementById('extension-internet-radio-now-playing');
            document.getElementById('extension-internet-radio-now-playing').addEventListener('click', (event) => {
                //console.log("copy?");
                this.clip('extension-internet-radio-now-playing'); 
                
			});
            
            
            // Search input enter press
			document.getElementById('extension-internet-radio-search-field').addEventListener('keyup', (event) => { // onEvent(e)
			    if (event.keyCode === 13) {
			        //console.log('Enter pressed');
					this.send_search();
			    }
			});
            
            // Search input button press
			document.getElementById('extension-internet-radio-search-button').addEventListener('click', (event) => {
				//console.log("send button clicked");
                this.send_search();
                
			});
			
            
            // Station name popup close
			document.getElementById('extension-internet-radio-input-popup').addEventListener('click', (event) => {
				console.log("popup clicked. event: ", event);
				if(event.target.getAttribute('id') == 'extension-internet-radio-input-popup'){
				    document.getElementById('extension-internet-radio-input-popup').classList.add('extension-internet-radio-hidden');
				}
			});
            
            // Station name popup save
            document.getElementById('extension-internet-radio-station-name-save-button').addEventListener('click', (event) => {
				//console.log("popup save button clicked. event: ", event);
                
                const new_name = document.getElementById('extension-internet-radio-station-name-input').value;
                const new_url = event.target.dataset.stream_url;
                
                if(new_name != ""){
    				window.API.postJson(
    					`/extensions/${this.id}/api/ajax`,
    					{'action':'add', 'name':new_name, 'stream_url':new_url}
    				).then((body) => { 
    					//console.log("add station reaction: ", body);
                        if(body.state == 'ok'){
                            //alert("The station was saved");
                        }
    				}).catch((e) => {
    					console.log("internet-radio: error in add station handler: ", e);
    					//pre.innerText = "Could not delete that station";
    				});
                    
                    document.getElementById('extension-internet-radio-station-name-input').value = "";
                    document.getElementById('extension-internet-radio-input-popup').classList.add('extension-internet-radio-hidden');
                }
                else{
                    alert("Please provide a name");
                }
                
			});
            
            
            
            
            // Easter egg: add custom station
            
			document.getElementById('extension-internet-radio-title').addEventListener('click', (event) => {
                if(!document.body.classList.contains('kiosk')){
                    if(confirm("Would you like to add a custom radio station?")){
                        const new_url = prompt('Please provide the URL of the stream');
                        const new_name = prompt('Please give this station a name');
                    
                        if(new_name != "" && new_url.startsWith('http')){
        					// Send new values to backend
        					window.API.postJson(
        						`/extensions/${this.id}/api/ajax`,
        						{'action':'add', 'name':new_name, 'stream_url':new_url}
        					).then((body) => { 
        						//console.log("add item reaction: ", body);
                                if(body.state = 'ok'){
                                    alert("The station has been added.");
                                    this.get_init_data();
                                }else{
                                    alert("Error: could not add station");
                                }
        					}).catch((e) => {
        						//console.log("internet-radio: error in add items handler: ", e);
        						//pre.innerText = "Could not delete that station";
                                alert("Error: could not add station");
        					});
                        }
                        else{
                            alert("That didn't seem right. Make sure the stream starts with http, and that you provided a name");
                        }
                    }
                }
				
			});
            
            
			// Add button
            document.getElementById('extension-internet-radio-add-button').addEventListener('click', (event) => {
                document.getElementById('extension-internet-radio-search-page').style.display = 'block';
                document.getElementById('extension-internet-radio-stations-page').style.display = 'none';
                
                document.getElementById('extension-internet-radio-back-button-container').classList.remove('extension-internet-radio-hidden');
                
                this.searching = true;
                // Only query the distribution server once
                if(!this.entered_search_page){
                    //console.log("getting server address of radio browser server");
                    this.entered_search_page = true;
                    this.get_radiobrowser_base_url_random()
                    .then((url) =>{
                        this.radio_browser_server = url;
                        //console.log("radiobrowser.info url: " + url);
                    });
                }
    			try{
                    this.stop_audio_in_browser();
    			}
    			catch(e){
    				//console.log("internet radio: could not stop audio in browser? " + e);
    			}
                
                // get a z-index above the main menu button while overlay with back button is active
                document.getElementById('extension-internet-radio-view').style.zIndex = '101';
                
			});
				
            // Back button
            document.getElementById('extension-internet-radio-back-button-container').addEventListener('click', (event) => {
                document.getElementById('extension-internet-radio-search-page').style.display = 'none';
                document.getElementById('extension-internet-radio-stations-page').style.display = 'block';
                document.getElementById('extension-internet-radio-input-popup').classList.add('extension-internet-radio-hidden');
                document.getElementById('extension-internet-radio-back-button-container').classList.add('extension-internet-radio-hidden');

                this.get_init_data();
                this.searching = false;
                
                // drop down to normal z-index
                document.getElementById('extension-internet-radio-view').style.zIndex = 'auto';
                
    			try{
                    this.stop_audio_in_browser();
    			}
    			catch(e){
    				//console.log("internet radio: could not stop audio in browser? " + e);
    			}    
			});
            
            
        
            this.get_init_data();
		}
		
	
    
        get_init_data(regenerate){
            
            if(typeof regenerate == 'undefined'){
                regenerate = true;
            }
            
			try{
				//pre.innerText = "";
				
		  		// Init
		        window.API.postJson(
		          `/extensions/${this.id}/api/ajax`,
                    {'action':'init'}

		        ).then((body) => {
                    
                    if(typeof body.debug != 'undefined'){
                        this.debug = body.debug;
                        if(body.debug == true){
                            console.log("Internet radio Init API result: ", body);
                            if(document.getElementById('extension-internet-radio-debug-warning') != null){
                                document.getElementById('extension-internet-radio-debug-warning').style.display = 'block';
                            }
                        }
                    }
                    
                    if(typeof body.volume != 'undefined'){
                        if(body.volume == 0){
                            if(document.getElementById('extension-internet-radio-volume-down-button') != null){
                                document.getElementById('extension-internet-radio-volume-down-button').classList.add('extension-internet-radio-volume-hidden');
                            }
                        }
                        this.previous_volume = body['volume'];
                    }
                    
                    this.station = body.station;
                    
                    this.playing = body.playing;
                    
                    if(document.body != null){
                        if(body.playing){
                            //console.log("icon should show playing state (pause icon)");
                            document.body.classList.add('extension-internet-radio-playing');
                        }
                        else{
                            //console.log("icon should show paused state (play icon)");
                            document.body.classList.remove('extension-internet-radio-playing');
                        }
                    }
                    
                    
                    
                    if(regenerate){
                        //console.log("regenerating radio stations view");
                        this.regenerate_items(body.stations);
                    }
                    
                    
                    this.show_buttons_everywhere = body.show_buttons_everywhere;
                    //console.log("this.show_buttons_everywhere is now: " + this.show_buttons_everywhere);
                    
                    if(regenerate || this.show_buttons_everywhere){
                        this.create_volume_and_play_buttons();
                        
                        if(this.interval == null){
                			this.interval = setInterval(() => {
				
                                const now_playing_element = document.getElementById('extension-internet-radio-now-playing');
                                try{
                                    // /poll
                    		        window.API.postJson(
                    		          `/extensions/${this.id}/api/ajax`,
                                        {'action':'poll'}

                    		        ).then((body) => {
                                        
                                        try{
                                            if(this.debug){
                                                console.log("internet radio poll: ", body);
                                            }
                                        
                                            // Playing
                                            if(typeof body.playing != 'undefined'){
                                                this.playing = body.playing;
                                                if(body.playing){
                                                    document.body.classList.add('extension-internet-radio-playing');
                                                }
                                                else{
                                                    document.body.classList.remove('extension-internet-radio-playing');
                                                    if(now_playing_element != null){
                                                        now_playing_element.innerText = '';
                                                    }
                                                
                                                }
                                                if(document.getElementById('extension-internet-radio-toggle-button') != null){
                                                    document.getElementById('extension-internet-radio-toggle-button').classList.remove('hidden');
                                                }
                                            
                                            }
                                        
                                        
                                            // Volume
                                            if(typeof body.volume != 'undefined'){
                                                //this.previous_volume = body['volume'];
                                                if(document.getElementById('extension-internet-radio-volume-indicator-line') != null){
                                                    document.getElementById('extension-internet-radio-volume-indicator-line').style.width = body['volume'] + "%";
                                                    //document.getElementById('extension-internet-radio-volume-indicator-container').classList.remove('extension-internet-radio-hidden');
                                                }
                                            }
                        
                                            // Now_playing
                                            if(typeof body.now_playing == 'string'){
                                                if(body.now_playing == "" || body.now_playing == null){
                                                    //document.getElementById('extension-internet-radio-now-playing-container').classList.remove('extension-internet-radio-has-now-playing');
                                                }
                                                else if(now_playing_element != null){
                                                    if(body.now_playing.indexOf('Advert') !== -1){
                                                        now_playing_element.innerText = 'Advertisement';
                                                    }else{
                                                        now_playing_element.innerText = body.now_playing;
                                                    }
                                                    //now_playing_element.style.width = (body.now_playing.length + 5) + 'ch';
                                                    //document.getElementById('extension-internet-radio-now-playing-container').classList.add('extension-internet-radio-has-now-playing');
                                                }
                                            }
                        
                                            // Station
                                            if(typeof body.station != 'undefined'){
                                                if(body.station != this.station && !this.searching){
                                                    //console.log("station was changed elsewhere");
                                                    // We're on the stations page, and the station was changed somewhere else
                                                    this.get_init_data();
                                                }
                            
                                                this.station = body.station;
                                            }
                                        
                                            if(typeof body.volume != 'undefined'){
                                                if(body['volume'] != this.previous_volume){
                                                    console.log("volume was changed elsewhere to: ", body['volume'] );
                                                    this.previous_volume = body['volume'];
                                                    //if(this.playing){
                                                        //this.volume_indicator_countdown = 4;
                                                        //if(document.getElementById('extension-internet-radio-volume-indicator-container') != null){
                                                        //    document.getElementById('extension-internet-radio-volume-indicator-container').classList.remove('extension-internet-radio-hidden');
                                                        //}
                                                    //}
                                                
                                                
                                                }
                                            }
                                        }
                                        catch(e){
                                            console.log("Error in try/catch inside /poll request: ", e);
                                        }
                                        
                    
                    		        }).catch((e) => {
                    		  			console.log("Error calling /poll: ", e);
                    		        });
                    
                                }
                                catch(e){
                                    console.log("Error doing poll: ", e);
                                }
                                
                                /*
                                if(this.volume_indicator_countdown > 0){
                                    this.volume_indicator_countdown--;
                                    if(document.getElementById('extension-internet-radio-volume-indicator-container') != null){
                                        if(this.volume_indicator_countdown == 0){
                                            document.getElementById('extension-internet-radio-volume-indicator-container').classList.add('extension-internet-radio-hidden');
                                        }
                                    }
                                }
                                */
				
                			}, 2000);
                        }
            			
                        
                    }
                    if(document.getElementById('extension-internet-radio-loading') != null){
                        document.getElementById('extension-internet-radio-loading').style.display = 'none';
                    }
                    

					
				
		        }).catch((e) => {
		  			console.log("Error getting InternetRadio init data: ", e);
		        });	

				
			}
			catch(e){
				console.log("Error in API call to init: ", e);
			}
        }
    
    
        //
        //  Create volume and play buttons.
        //
        
    
        create_volume_and_play_buttons(){
            try{
                var target_to_attach_buttons_to = document.getElementById('extension-internet-radio-content-container');
            
                if(this.show_buttons_everywhere){
                    target_to_attach_buttons_to = document.body;
                }
            
                //console.log("target_to_attach_buttons_to: ", target_to_attach_buttons_to);
            
            
                // Check if the buttons need to be added.
            
                // Adding volume down button
                if(document.getElementById('extension-internet-radio-volume-down-button') == null){
                    //console.log("adding volume down button");
                    var down_button = document.createElement('button');
                    down_button.setAttribute("id","extension-internet-radio-volume-down-button");
                    down_button.setAttribute("class","icon-button");
                    down_button.setAttribute("aria-label","volume down");
                    target_to_attach_buttons_to.append(down_button);
                
                    // Volume down
                    document.getElementById('extension-internet-radio-volume-down-button').addEventListener('click', (event) => {
                        //console.log("volume down button clicked");
                        
        		        window.API.postJson(
        		          `/extensions/${this.id}/api/ajax`,
                            {'action':'volume_down'}

        		        ).then((body) => {
                            if(this.debug){
                                console.log("Volume down response: ", body);
                            }
                            
                            // Show volume indicator
                            //this.volume_indicator_countdown = 4;
                            this.previous_volume = body['volume'];
                            if(document.getElementById('extension-internet-radio-volume-indicator-line') != null){
                                document.getElementById('extension-internet-radio-volume-indicator-line').style.width = body['volume'] + "%";
                            }
                            //document.getElementById('extension-internet-radio-volume-indicator-container').classList.remove('extension-internet-radio-hidden');
                            
                            
                            if(body.volume == 0){
                                document.getElementById('extension-internet-radio-volume-down-button').classList.add('extension-internet-radio-volume-hidden');
                            }
				
        		        }).catch((e) => {
        		  			console.log("Error lowering radio volume: ",e);
        		        });	
        			});
                }
            
            
                // Adding volume indicator
                if(document.getElementById('extension-internet-radio-volume-indicator-container') == null){
                    var indicator_el = document.createElement('div');
                    indicator_el.setAttribute("id","extension-internet-radio-volume-indicator-container");
                    //if(this.playing == false){
                    //    indicator_el.classList.add('extension-internet-radio-hidden');
                    //}
                    var indicator2_el = document.createElement('div');
                    indicator2_el.setAttribute("id","extension-internet-radio-volume-indicator-line");
                    indicator2_el.style.width = this.previous_volume + "%";
                    indicator_el.append(indicator2_el);
                    target_to_attach_buttons_to.append(indicator_el);
                    
                    this.volume_indicator_countdown = 4;
                    
                }
            
            
                // Adding volume up button
                if(document.getElementById('extension-internet-radio-volume-up-button') == null){
                    //console.log("adding volume up button");
                    var up_button = document.createElement('button');
                    up_button.setAttribute("id","extension-internet-radio-volume-up-button");
                    up_button.setAttribute("class","icon-button");
                    up_button.setAttribute("aria-label","volume up");
                    target_to_attach_buttons_to.append(up_button);
                
                    // Volume up
                    document.getElementById('extension-internet-radio-volume-up-button').addEventListener('click', (event) => {
                        //console.log("volume up button clicked");
                
        		        window.API.postJson(
        		          `/extensions/${this.id}/api/ajax`,
                            {'action':'volume_up'}

        		        ).then((body) => {
                            if(this.debug){
                                console.log("Volume up response: ", body);
                            }
        					
                            // Show volume indicator
                            this.volume_indicator_countdown = 4;
                            this.previous_volume = body['volume'];
                            if(document.getElementById('extension-internet-radio-volume-indicator-line') != null){
                                document.getElementById('extension-internet-radio-volume-indicator-line').style.width = body['volume'] + "%";
                                //document.getElementById('extension-internet-radio-volume-indicator-container').classList.remove('extension-internet-radio-hidden');
                            }
                            
        					//console.log(body);
                            document.getElementById('extension-internet-radio-volume-down-button').classList.remove('extension-internet-radio-volume-hidden');
                        
        		        }).catch((e) => {
        		  			console.log("Error raising radio volume: ",e);
        		        });	
        			});
                }
            
                if(document.getElementById('extension-internet-radio-toggle-button') == null){
                    //console.log("adding radio toggle button");
                    var toggle_button = document.createElement('button');
                    toggle_button.setAttribute("id","extension-internet-radio-toggle-button");
                    toggle_button.setAttribute("class","icon-button");
                    toggle_button.setAttribute("aria-label","play or pause");
                
                    toggle_button.addEventListener('click', (event) => {
                        //console.log("top-right stop button clicked");
            
        		        window.API.postJson(
        		          `/extensions/${this.id}/api/ajax`,
                            {'action':'toggle'}

        		        ).then((body) => {
        					//console.log("Toggle result:");
        					//console.log(body);
                            if(typeof body.playing != 'undefined'){
                                if(body.playing){
                                    //console.log("icon should show playing state (pause icon)");
                                    document.body.classList.add('extension-internet-radio-playing');
                                }
                                else{
                                    //console.log("icon should show paused state (play icon)");
                                    document.body.classList.remove('extension-internet-radio-playing');
                                    if(document.getElementById('extension-internet-radio-now-playing') != null){
                                        document.getElementById('extension-internet-radio-now-playing').innerText = "";
                                    }
                                    //if(document.getElementById('extension-internet-radio-volume-indicator-container') != null){
                                    //    document.getElementById('extension-internet-radio-volume-indicator-container').classList.add('extension-internet-radio-hidden');
                                    //}
                                    
                                    
                                }
                                this.get_init_data(); //update the stations to show which one is playing.
                            }
			
        		        }).catch((e) => {
        		  			console.log("Error toggling radio: ", e);
        		        });	
                    });
                    target_to_attach_buttons_to.append(toggle_button);
                }
            

           
           
            }
            catch(e){
                console.log("internet radio: add volume and toggle buttons error: ", e);
            }
            
            
        }
    
    
    
    
    
    
    
    
    
    
    
    
    
    
	
        //
        //  SEARCH
        //
        
		send_search(options){
            var items = [];
            
            
            if(typeof options == 'undefined'){
                options = {};
            }
            
            // Query type
            var query_type = 'search';
            if(typeof options.query_type != 'undefined') {
                //console.log(options.query_type);
                query_type = options.query_type;
            }
            
            
            // LIMIT
            // If no amount provided, set default
            /*
            if(typeof amount == 'undefined'){
                amount = 20;
                if(this.get_more_search_results){
                    
                }
            }
            */
            const amount = 100;
            items.push('limit=' + encodeURIComponent(amount));
            //console.log("Search amount: ", amount);
            
            
            // NAME
            var text = "";
            if(query_type == 'search'){
                text = document.getElementById('extension-internet-radio-search-field').value;
            }
            if(text != ""){
                items.push('name=' + encodeURIComponent(text));
			}
            
            
            // COUNTRY
            const countrycode = document.getElementById('extension-internet-radio-countries-dropdown').value;
            //console.log("country code: " + countrycode);
            if(countrycode != 'ALL'){
                items.push('countrycode=' + encodeURIComponent(countrycode));
            }
            
            /*
            if (search_data.state) {
                items.push('state=' + encodeURIComponent(search_data.state));
            }
            
            if (search_data.tag) {
                items.push('tag=' + encodeURIComponent(search_data.tag));
            }
            */
            
            //items.push('order=' + encodeURIComponent('random'));
            
            
            
            
            var api_path = this.radio_browser_server + '/json/stations/lastclick?limit=20&offset=' + Math.floor(Math.random() * 20) * 20;
            
            //console.log("items and length: ", items, items.length);
            
            if(items.length > 1){
                if(query_type == 'search'){
                    api_path = this.radio_browser_server + '/json/stations/' + query_type + '?' + items.join('&');   
                }
                
            }
            else if(query_type == 'bytagexact'){
                //console.log("searching by exact tag");
                if(typeof options.tag != 'undefined'){
                    api_path = this.radio_browser_server + '/json/stations/' + query_type + '/'  + options.tag + '?' + items.join('&');   
                }
            }
            else{
                //console.log("doing a last_click search (semi-random)");
            }

            //console.log("api_path = ", api_path);

            this.radio_search(api_path).then((found_stations) =>{
                //console.log("search result: ", found_stations);
                this.regenerate_items(found_stations, "search");
            });


            //get_radiobrowser_server_config(url)
            //.then((config) =>{
            //    //console.log("got config: ", config);
            //});
            
		}
        
        
        
        
    
	
		//
		//  REGENERATE ITEMS
		//
	
		regenerate_items(items, page){
			try {
				//console.log("regenerating. items: ", items);
		        var list = document.getElementById('extension-internet-radio-stations-list');
                if(list == null){
                    return;
                }
                
				//const pre = document.getElementById('extension-internet-radio-response-data');
				
				const original = document.getElementById('extension-internet-radio-original-item');
			    //console.log("original: ", original);
                
                if(typeof items == 'undefined'){
                    items = this.stations;
                }
			
				items.sort((a, b) => (a.name.toLowerCase() > b.name.toLowerCase()) ? 1 : -1) // sort alphabetically
				
                
                
                if(page == 'search'){
                    list = document.getElementById('extension-internet-radio-search-results-list');
                    //list.innerHTML = '<span id="extension-internet-radio-text-response-field">Search results:</span>';
                }
                
                if(items.length == 0){
                    list.innerHTML = "No results";
                }
                else{
                    list.innerHTML = "";
                }
                
				// Loop over all items
				for( var item in items ){
					
					var clone = original.cloneNode(true);
					clone.removeAttribute('id');
                    
                    var station_name = "Error";
                    var stream_url = "Error";
                    
                    if(page == 'search'){
                        station_name = items[item].name;
                        stream_url = items[item].url_resolved;
                        
                        // Add tags
                        if(typeof items[item].tags != "undefined"){
                            const tags_array = items[item].tags.split(",");
                            const tags_container = clone.getElementsByClassName("extension-internet-radio-item-tags")[0]
                            for (var i = 0; i < tags_array.length; i++) {
            					if(tags_array[i].length > 2){
                                    var s = document.createElement("span");
                					s.classList.add('extension-internet-radio-tag');                
                					var t = document.createTextNode(tags_array[i]);
                					s.appendChild(t);
                                    s.addEventListener('click', (event) => {
                                        //console.log('clicked on tag: ', event.target.innerText);
                                        this.send_search({'query_type':'bytagexact','tag':event.target.innerText})
                                    });
                                    tags_container.append(s);
                                }
                                
                            }
                            
                            //clone.getElementsByClassName("extension-internet-radio-item-tags")[0].innerText = items[item].tags;
                        }
                        
                    }
                    else{
                        station_name = items[item].name;
                        stream_url = items[item].stream_url;
                    }
                    
                    // Remove potential tracking data from URL
                    if(stream_url.indexOf('?') !== -1){
                        //console.log("removing potential tracking string from: " + stream_url );
                        stream_url = stream_url.substring(0, stream_url.indexOf('?'));
                    }
                    
                    // Remove ; character that sometimes is present at the end of the URL
                    //if( stream_url.slice(-1) == ';'){
                    //    stream_url = stream_url.slice(0, stream_url.length - 1);
                    //}
                    
                    
                    
                    clone.getElementsByClassName("extension-internet-radio-item-title")[0].innerText = station_name;
                    clone.getElementsByClassName("extension-internet-radio-item-url")[0].innerText = stream_url;
                    
                    if(station_name == this.station && this.playing){
                        clone.classList.add('extension-internet-radio-item-playing');   
                    }
                    
                    
                    //var title_element = clone.getElementsByClassName("extension-internet-radio-item-title")[0];

                    if(page == 'search'){
                        
    					
                        // ADD station button
    					const add_button = clone.querySelectorAll('.extension-internet-radio-item-action-button')[0];
                        //console.log("add button? ", add_button);
                        add_button.setAttribute('data-stream_url', stream_url);
    					add_button.addEventListener('click', (event) => {
                            //console.log("click event: ", event);
                            
                            document.getElementById('extension-internet-radio-input-popup').classList.remove('extension-internet-radio-hidden');
                            document.getElementById('extension-internet-radio-station-name-save-button').setAttribute("data-stream_url", event.target.dataset.stream_url);
                            
                            //const new_name = prompt('Please give this station a name');
                            //const new_url = event.target.dataset.stream_url;
                            
    						var target = event.currentTarget;
    						var parent3 = target.parentElement.parentElement.parentElement;
    						parent3.classList.add("extension-internet-radio-item-added"); // well... maybe
    				  	});
                        
                    }
                    else{
                        
    					// DELETE button
    					const delete_button = clone.querySelectorAll('.extension-internet-radio-item-action-button')[0];
                        //console.log("delete button? ", delete_button);
                        delete_button.setAttribute('data-name', station_name);
                        
    					delete_button.addEventListener('click', (event) => {
                            //console.log("click event: ", event);
                            if(confirm("Are you sure you want to delete this station?")){
        						var target = event.currentTarget;
        						var parent3 = target.parentElement.parentElement.parentElement;
        						parent3.classList.add("extension-internet-radio-item-delete");
        						var parent4 = parent3.parentElement;
    						
					
        						// Send new values to backend
        						window.API.postJson(
        							`/extensions/${this.id}/api/ajax`,
        							{'action':'delete','name': event.target.dataset.name}
        						).then((body) => { 
        							//console.log("delete item reaction: ", body);
                                    if(body.state == 'ok'){
                                        parent4.removeChild(parent3);
                                    }

        						}).catch((e) => {
        							console.log("internet-radio: error in delete items handler: ", e);
        							//pre.innerText = "Could not delete that station"
                                    parent3.classList.remove("extension-internet-radio-item-delete");
        						});
                            }
    				  	});
                    }

					
					
                    
                    // preview
					const preview_button = clone.querySelectorAll('.extension-internet-radio-preview')[0];
                    //console.log("preview_button: ", preview_button);
                    preview_button.setAttribute('data-stream_url', stream_url);
                    preview_button.setAttribute('data-playing', false);
                    
					preview_button.addEventListener('click', (event) => {
                        const playing = event.target.dataset.playing;
                        //console.log("playing: ", playing);
                        if(playing == "true"){
                            //console.log("should stop audio");
                            this.stop_audio_in_browser();
                            //preview_button.setAttribute('data-playing', false);
                        }
                        else{
                            const preview_buttons = document.querySelectorAll('.extension-internet-radio-preview');
                            //console.log("preview_buttons.length: " + preview_buttons.length);
                            for (var i = 0; i < preview_buttons.length; ++i) {
                                preview_buttons[i].dataset.playing = "false";
                            }
                            preview_button.setAttribute('data-playing', true);
                            const preview_url = event.target.dataset.stream_url;
                            this.play_audio_in_browser(preview_url);
                        }
                        
                        
					    
                        
                        //document.getElementById('extension-internet-radio-toggle-button').style.display = 'block';
					});
                    
                    
                    
                    // Big play buttons on items. They always turn on a stream.
					const play_button = clone.querySelectorAll('.extension-internet-radio-play-icon')[0];
                    play_button.setAttribute('data-stream_url', stream_url);
					play_button.addEventListener('click', (event) => {
					    //console.log("event: ", event);
                        //console.log(event.path[2]);
                        
                        try{
                            const playing_items = document.querySelectorAll('.extension-internet-radio-item-playing');
                            for (var i = 0; i < playing_items.length; ++i) {
                                playing_items[i].classList.remove('extension-internet-radio-item-playing');
                            }
                            event.path[2].classList.add('extension-internet-radio-item-playing');
                            document.getElementById('extension-internet-radio-now-playing').innerText = "";
                        }
                        catch (e){
                            console.log('Error with play button: ', e);
                        }
                        
                        
                        //console.log("play");
                        const play_url = event.target.dataset.stream_url;
                        //console.log("play_url: ", play_url);
                        
						// Send new values to backend
						window.API.postJson(
							`/extensions/${this.id}/api/ajax`,
							{'action':'play','stream_url': play_url}
						).then((body) => { 
							if(this.debug){
							    console.log("debug: play reaction: ", body);
							}
                            if(body.state == 'ok'){
                                play_button.setAttribute('data-playing', true);
                                this.playing = true;
                                document.body.classList.add('extension-internet-radio-playing');
                            }
                            

						}).catch((e) => {
							console.log("internet-radio: play button: error: ", e);
							//pre.innerText = "Could not delete that station"
						});
                        
                        
					});
                    
                    
                    
                    
                    
					//clone.classList.add('extension-internet-radio-type-' + type);
					//clone.querySelectorAll('.extension-internet-radio-type' )[0].classList.add('extension-internet-radio-icon-' + type);
					

				    /*
					var s = document.createElement("span");
					s.classList.add('extension-internet-radio-thing');                
					var t = document.createTextNode("bla");
					s.appendChild(t);                                           
					clone.querySelectorAll('.extension-internet-radio-change' )[0].appendChild(s);
                    */
                    
				    //console.log('list? ', list);
					list.append(clone);
                    
                    
                    
				} // end of for loop
			    //console.log("more button? items.length: ", items.length);
                if(page == 'search' && this.get_more_search_results == false){
                    
                    //console.log("should add more button")
					var s = document.createElement("button");
					s.setAttribute("id", "extension-internet-radio-search-more-button");          
					var t = document.createTextNode("More");
					s.appendChild(t);
                    //console.log(s);
                    s.addEventListener('click', (event) => {
                        //console.log("get more button clicked");
                        this.get_more_search_results = true;
                        this.send_search();
                        
				    });
                    
                    //console.log("appending more button");
					list.appendChild(s);
                }
                
                //const get_more_button = document.getElementById('extension-internet-radio-search-more-button');
                
                //get_more_button
            
            
			}
			catch (e) {
				// statements to handle any exceptions
				console.log("Error in regenerate_items: ", e); // pass exception object to error handler
			}
		}
	
    
    
    
    
    
        play_audio_in_browser(url){
            //document.getElementById('extension-internet-radio-audio-player').src = url;
            //console.log("start audio");
            
            if(typeof document.getElementById('extension-internet-radio-view').audio_player == 'undefined'){
                //console.log("audio player didn't exist yet? making it now");
                document.getElementById('extension-internet-radio-view').audio_player = new Audio(url);
            }else{
                //console.log("feeding audio player new url: " + url);
                document.getElementById('extension-internet-radio-view').audio_player.pause();
                document.getElementById('extension-internet-radio-view').audio_player.src = url;
            }
            
            document.getElementById('extension-internet-radio-view').audio_player.play();
        }
    
        stop_audio_in_browser(){
            //console.log("stop audio");
            document.getElementById('extension-internet-radio-view').audio_player.pause();
            document.getElementById('extension-internet-radio-view').audio_player.src = "";
            try{
                const preview_buttons = document.querySelectorAll('.extension-internet-radio-preview');
                for (var i = 0; i < preview_buttons.length; ++i) {
                    preview_buttons[i].dataset.playing = "false";
                }
            }
            catch(e){
                console.log("Error stopping radio audio preview in browser: ", e);
            }
            
        }
    
    
    
    
        /**
         * Ask a specified server for a list of all other server.
         */
        get_radiobrowser_base_urls() {
            return new Promise((resolve, reject)=>{
                var request = new XMLHttpRequest()
                // If you need https, please use the fixed server fr1.api.radio-browser.info for this request only
                request.open('GET', 'http://all.api.radio-browser.info/json/servers', true);
                request.onload = function() {
                    if (request.status >= 200 && request.status < 300){
                        var items = JSON.parse(request.responseText).map(x=>"https://" + x.name);
                        resolve(items);
                    }else{
                        reject(request.statusText);
                    }
                }
                request.send();
            });
        }

        /**
         * Ask a server for its settings.
         */
        get_radiobrowser_server_config(baseurl) {
            return new Promise((resolve, reject)=>{
                var request = new XMLHttpRequest()
                request.open('GET', baseurl + '/json/config', true);
                request.onload = function() {
                    if (request.status >= 200 && request.status < 300){
                        var items = JSON.parse(request.responseText);
                        resolve(items);
                    }else{
                        reject(request.statusText);
                    }
                }
                request.send();
            });
        }

        /**
         * Get a random available radio-browser server.
         * Returns: string - base url for radio-browser api
         */
        get_radiobrowser_base_url_random() {
            return this.get_radiobrowser_base_urls().then(hosts => {
                var item = hosts[Math.floor(Math.random() * hosts.length)];
                return item;
            });
        }


        // search
        radio_search(baseurl, name) {
            return new Promise((resolve, reject)=>{
                var request = new XMLHttpRequest()
                request.open('GET', baseurl, true);
                //request.setRequestHeader("User-Agent", "webthingsio/internet-radio"); //  I keep seeing "refused to send unsafe header". Sorry radio-browser.info, I tried!"
                request.onload = function() {
                    if (request.status >= 200 && request.status < 300){
                        var items = JSON.parse(request.responseText);
                        resolve(items);
                    }else{
                        reject(request.statusText);
                    }
                }
                request.send();
            });
        }
    
    
        // Copy to clipboard
        clip(element_id) {
            var range = document.createRange();
            range.selectNode(document.getElementById(element_id));
            window.getSelection().removeAllRanges(); // clear current selection
            window.getSelection().addRange(range); // to select text
            document.execCommand("copy");
            window.getSelection().removeAllRanges();// to deselect
            alert("Copied song name to clipboard");
        }
    
    
    }

	new InternetRadio();
	
})();


