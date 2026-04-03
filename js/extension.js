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
			
			this.page_visible = true;
			document.addEventListener("visibilitychange", () => {
			  if (document.hidden) {
				  this.page_visible = false;
			  } else {
				  this.page_visible = true;
			  }
			});
            
            this.interval = null;
			this.attempts = 0;
			this.retried_init_once = false;

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
            
            this.busy_polling = false;
            //this.busy_polling_counter = 0;
            
            
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
            
			
			if(this.content == ''){
				return;
			}
			else{
				this.view.innerHTML = this.content;
			}
			
			this.view.audio_player = new Audio();
			//console.log("audio player: ", this.view.audio_player);

			const list = document.getElementById('extension-internet-radio-list');
		
			const pre = document.getElementById('extension-internet-radio-response-data');
            
			document.getElementById('menu-button').classList.remove('hidden');
			
			
            // Copy to clipboard
			const now_playing_el = this.view.querySelector('#extension-internet-radio-now-playing');
			if(now_playing_el){
	            now_playing_el.addEventListener('click', (event) => {
	                //console.log("copy?");
	                this.clip('extension-internet-radio-now-playing'); 
                
				});
			}
            
            
            
            // Search input enter press
			this.view.querySelector('#extension-internet-radio-search-field').addEventListener('keyup', (event) => { // onEvent(e)
			    if (event.keyCode === 13) {
			        //console.log('Enter pressed');
					this.send_search();
			    }
			});
            
            // Search input button press
			this.view.querySelector('#extension-internet-radio-search-button').addEventListener('click', (event) => {
				//console.log("send button clicked");
                this.send_search();
                
			});
			
            
            // Station name popup close
			this.view.querySelector('#extension-internet-radio-input-popup').addEventListener('click', (event) => {
				console.log("popup clicked. event: ", event);
				if(event.target.getAttribute('id') == 'extension-internet-radio-input-popup'){
				    this.view.querySelector('#extension-internet-radio-input-popup').classList.add('extension-internet-radio-hidden');
				}
			});
            
            // Station name popup save
            this.view.querySelector('#extension-internet-radio-station-name-save-button').addEventListener('click', (event) => {
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
                    
                    this.view.querySelector('#extension-internet-radio-station-name-input').value = "";
                    this.view.querySelector('#extension-internet-radio-input-popup').classList.add('extension-internet-radio-hidden');
                }
                else{
                    alert("Please provide a name");
                }
                
			});
            
            
            
            
            // Easter egg: add custom station
            
			this.view.querySelector('#extension-internet-radio-title').addEventListener('click', (event) => {
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
            this.view.querySelector('#extension-internet-radio-add-button').addEventListener('click', (event) => {
                this.view.querySelector('#extension-internet-radio-search-page').style.display = 'block';
                this.view.querySelector('#extension-internet-radio-stations-page').style.display = 'none';
                
                this.view.querySelector('#extension-internet-radio-back-button-container').classList.remove('extension-internet-radio-hidden');
                
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
                this.view.style.zIndex = '101';
                
			});
				
            // Back button
            this.view.querySelector('#extension-internet-radio-back-button-container').addEventListener('click', (event) => {
                this.view.querySelector('#extension-internet-radio-search-page').style.display = 'none';
                this.view.querySelector('#extension-internet-radio-stations-page').style.display = 'block';
                this.view.querySelector('#extension-internet-radio-input-popup').classList.add('extension-internet-radio-hidden');
                this.view.querySelector('#extension-internet-radio-back-button-container').classList.add('extension-internet-radio-hidden');

                this.get_init_data();
                this.searching = false;
                
                // drop down to normal z-index
                this.view.style.zIndex = 'auto';
                
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
            
	  		// Init
	        window.API.postJson(
	          `/extensions/${this.id}/api/ajax`,
                {'action':'init'}

	        ).then((body) => {
                this.parse_init(body,regenerate);

	        }).catch((err) => {
	  			console.log("internet radio: caught error getting InternetRadio init data: ", err);
				setTimeout(() => {
					if(this.retried_init_once == false){
						this.retried_init_once = true;
						this.get_init_data(regenerate);
					}
				},10000);
	        });	
        }
		
		
		
		parse_init(body,regenerate){
			
            if(typeof body.debug != 'undefined'){
                this.debug = body.debug;
                if(this.debug){
                    console.log("Internet radio debug: API init response: ", body);
					const debug_warning_el = this.view.querySelector('#extension-internet-radio-debug-warning');
                    if(debug_warning_el){
                        debug_warning_el.style.display = 'block';
                    }
                }
            }
            
            if(typeof body.volume != 'undefined'){
                if(body.volume == 0){
					const volume_down_button_el = document.getElementById('extension-internet-radio-volume-down-button');
                    if(volume_down_button_el){
                        volume_down_button_el.classList.add('extension-internet-radio-volume-hidden');
                    }
                }
                this.previous_volume = body['volume'];
            }
            
			if(typeof body.station == 'string'){
            	this.station = body.station;
			}
            
			if(typeof body.playing == 'boolean'){
            	this.playing = body.playing;
	            if(document.body){
	                if(body.playing){
	                    //console.log("icon should show playing state (pause icon)");
	                    document.body.classList.add('extension-internet-radio-playing');
	                }
	                else{
	                    //console.log("icon should show paused state (play icon)");
	                    document.body.classList.remove('extension-internet-radio-playing');
	                }
	            }
			}
            
            
            if(typeof body.stations != 'undefined' && regenerate){
                //console.log("regenerating radio stations view");
                this.regenerate_items(body.stations);
            }
            
            
            this.show_buttons_everywhere = body.show_buttons_everywhere;
            //console.log("this.show_buttons_everywhere is now: " + this.show_buttons_everywhere);
            
            if(regenerate || this.show_buttons_everywhere){
                this.create_volume_and_play_buttons();
                
                if(this.interval == null){
        			this.interval = setInterval(() => {
		
                        // /poll
                        if(this.page_visible && this.busy_polling == false){
							this.busy_polling = true;
							
            		        window.API.postJson(
            		          `/extensions/${this.id}/api/ajax`,
                                {'action':'poll'}

            		        ).then((body) => {
                                if(this.debug && window.location.pathname == '/extensions/internet-radio'){
                                    console.log("internet radio debug: poll response: ", body);
                                }
                                this.busy_polling = false;
                                this.parse_poll(body);
							
            		        }).catch((err) => {
            		  			console.error("internet radio: caught error calling /poll: ", err);
								this.busy_polling = false;
            		        });
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
			const loading_el = document.getElementById('extension-internet-radio-loading');
            if(loading_el){
                loading_el.style.display = 'none';
            }
            
		}
    
	
		parse_poll(body){
			
			const now_playing_el = this.view.querySelector('#extension-internet-radio-now-playing');
			
            // Playing
            if(typeof body.playing != 'undefined'){
                this.playing = body.playing;
                if(body.playing){
                    document.body.classList.add('extension-internet-radio-playing');
                }
                else{
                    document.body.classList.remove('extension-internet-radio-playing');
                    if(now_playing_el != null){
                        now_playing_el.textContent = '';
                    }
                
                }
				const internet_radio_toggle_button_el = document.getElementById('extension-internet-radio-toggle-button');
                if(internet_radio_toggle_button_el){
                    internet_radio_toggle_button_el.classList.remove('hidden');
                }
            
            }
        
        
            // Volume
            if(typeof body.volume != 'undefined'){
                //this.previous_volume = body['volume'];
				const internet_radio_volume_indicator_line_el = document.getElementById('extension-internet-radio-volume-indicator-line');
                if(internet_radio_volume_indicator_line_el){
                    internet_radio_volume_indicator_line_el.style.width = body['volume'] + "%";
                    //document.getElementById('extension-internet-radio-volume-indicator-container').classList.remove('extension-internet-radio-hidden');
                }
            }

            // Now_playing
            if(typeof body.now_playing == 'string'){
                if(body.now_playing == "" || body.now_playing == null){
                    //document.getElementById('extension-internet-radio-now-playing-container').classList.remove('extension-internet-radio-has-now-playing');
                }
                else if(now_playing_el != null){
                    if(body.now_playing.indexOf('Advert') !== -1){
                        now_playing_el.innerText = 'Advertisement';
                    }else{
                        now_playing_el.innerText = body.now_playing;
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
                    if(this.debug){
						console.log("internet radio debug: volume was changed elsewhere from: " + this.previous_volume + ", to: " + body['volume'] );
					}
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
	
	
    
        //
        //  Create volume and play buttons.
        //
        
    
        create_volume_and_play_buttons(){
            try{
                var target_to_attach_buttons_to = this.view.querySelector('#extension-internet-radio-content-container');
            
                if(this.show_buttons_everywhere){
                    target_to_attach_buttons_to = document.body;
                }
            
                //console.log("target_to_attach_buttons_to: ", target_to_attach_buttons_to);
            
            
                // Check if the buttons need to be added.
            
                // Adding volume down button
				
				let toggle_button_el = document.getElementById('extension-internet-radio-toggle-button');
				let volume_up_button_el = document.getElementById('extension-internet-radio-volume-up-button');
				let volume_indicator_line_el = document.getElementById('extension-internet-radio-volume-indicator-line');
				let volume_down_button_el = document.getElementById('extension-internet-radio-volume-down-button');
				
				
                if(volume_down_button_el == null){
                    //console.log("adding volume down button");
                    volume_down_button_el = document.createElement('button');
                    volume_down_button_el.setAttribute("id","extension-internet-radio-volume-down-button");
                    volume_down_button_el.setAttribute("class","icon-button");
                    volume_down_button_el.setAttribute("aria-label","volume down");
                    target_to_attach_buttons_to.append(volume_down_button_el);
                
                    // Volume down
					volume_down_button_el.addEventListener('click', () => {
                        //console.log("volume down button clicked");
                        
        		        window.API.postJson(
        		          `/extensions/${this.id}/api/ajax`,
                            {'action':'volume_down'}

        		        ).then((body) => {
                            if(this.debug){
                                console.log("internet radio debug: volume down response: ", body);
                            }
                            
                            // Show volume indicator
                            //this.volume_indicator_countdown = 4;
                            this.previous_volume = body['volume'];
							
                            if(volume_indicator_line_el){
                                volume_indicator_line_el.style.width = body['volume'] + "%";
                            }
                            //document.getElementById('extension-internet-radio-volume-indicator-container').classList.remove('extension-internet-radio-hidden');
                            
                            
                            if(body.volume == 0){
                                volume_down_button_el.classList.add('extension-internet-radio-volume-hidden');
                            }
				
        		        }).catch((err) => {
        		  			console.log("internet radio: caught error lowering radio volume: ", err);
        		        });	
        			});
                }
            
            
                // Adding volume indicator
                if(volume_indicator_line_el == null){
                    var indicator_container_el = document.createElement('div');
                    indicator_container_el.setAttribute("id","extension-internet-radio-volume-indicator-container");
                    //if(this.playing == false){
                    //    indicator_el.classList.add('extension-internet-radio-hidden');
                    //}
                    volume_indicator_line_el = document.createElement('div');
                    volume_indicator_line_el.setAttribute("id","extension-internet-radio-volume-indicator-line");
                    volume_indicator_line_el.style.width = this.previous_volume + "%";
                    indicator_container_el.append(volume_indicator_line_el);
                    target_to_attach_buttons_to.append(indicator_container_el);
                    
                    this.volume_indicator_countdown = 4;
                    
                }
            
				
            
                // Adding volume up button
                if(volume_up_button_el == null){
                    //console.log("adding volume up button");
                    volume_up_button_el = document.createElement('button');
                    volume_up_button_el.setAttribute("id","extension-internet-radio-volume-up-button");
                    volume_up_button_el.setAttribute("class","icon-button");
                    volume_up_button_el.setAttribute("aria-label","volume up");
                    volume_up_button_el.addEventListener('click', () => {
                        //console.log("volume up button clicked");
                
        		        window.API.postJson(
        		          `/extensions/${this.id}/api/ajax`,
                            {'action':'volume_up'}

        		        ).then((body) => {
                            if(this.debug){
                                console.log("internet radio debug: volume up response: ", body);
                            }
        					
                            // Show volume indicator
                            this.volume_indicator_countdown = 4;
                            this.previous_volume = body['volume'];
                            if(volume_indicator_line_el){
                                volume_indicator_line_el.style.width = body['volume'] + "%";
                                //document.getElementById('extension-internet-radio-volume-indicator-container').classList.remove('extension-internet-radio-hidden');
                            }
                            
        					//console.log(body);
							if(volume_down_button_el){
								volume_down_button_el.classList.remove('extension-internet-radio-volume-hidden');
							}
                            
                        
        		        }).catch((err) => {
        		  			console.error("internet radio: caught error raising radio volume: ", err);
        		        });	
        			});
					target_to_attach_buttons_to.append(volume_up_button_el);
                }
            
                if(toggle_button_el == null){
                    //console.log("adding radio toggle button");
                    toggle_button_el = document.createElement('button');
                    toggle_button_el.setAttribute("id","extension-internet-radio-toggle-button");
                    toggle_button_el.setAttribute("class","icon-button");
                    toggle_button_el.setAttribute("aria-label","play or pause");
                
                    toggle_button_el.addEventListener('click', () => {
                        //console.log("top-right stop button clicked");
            
        		        window.API.postJson(
        		          `/extensions/${this.id}/api/ajax`,
                            {'action':'toggle'}

        		        ).then((body) => {
        					//console.log("Toggle result:");
        					//console.log(body);
                            if(typeof body.playing == 'boolean'){
                                if(body.playing){
                                    //console.log("icon should show playing state (pause icon)");
                                    document.body.classList.add('extension-internet-radio-playing');
                                }
                                else{
                                    //console.log("icon should show paused state (play icon)");
                                    document.body.classList.remove('extension-internet-radio-playing');
									const now_playing_el = document.getElementById('extension-internet-radio-now-playing');
                                    if(now_playing_el){
                                        now_playing_el.textContent = '';
                                    }
                                    //if(document.getElementById('extension-internet-radio-volume-indicator-container') != null){
                                    //    document.getElementById('extension-internet-radio-volume-indicator-container').classList.add('extension-internet-radio-hidden');
                                    //}
                                    
                                    
                                }
                                this.get_init_data(); //update the stations to show which one is playing.
                            }
			
        		        }).catch((err) => {
        		  			console.error("internet radio: caught error toggling radio: ", err);
        		        });	
                    });
                    target_to_attach_buttons_to.append(toggle_button_el);
                }
            

            }
            catch(err){
                console.error("internet radio: caught general error adding volume and toggle buttons: ", err);
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
                text = this.view.querySelector('#extension-internet-radio-search-field').value;
            }
            if(text != ""){
                items.push('name=' + encodeURIComponent(text));
			}
            
            
            // COUNTRY
            const countrycode = this.view.querySelector('#extension-internet-radio-countries-dropdown').value;
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
		        var list = this.view.querySelector('#extension-internet-radio-stations-list');
                if(list == null){
                    return;
                }
                
				//const pre = document.getElementById('extension-internet-radio-response-data');
				
				const original = this.view.querySelector('#extension-internet-radio-original-item');
			    //console.log("original: ", original);
                
                if(typeof items == 'undefined'){
                    items = this.stations;
                }
			
				items.sort((a, b) => (a.name.toLowerCase() > b.name.toLowerCase()) ? 1 : -1) // sort alphabetically
				
                
                
                if(page == 'search'){
                    list = this.view.querySelector('#extension-internet-radio-search-results-list');
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
                            
                            this.view.querySelector('#extension-internet-radio-input-popup').classList.remove('extension-internet-radio-hidden');
                            this.view.querySelector('#extension-internet-radio-station-name-save-button').setAttribute("data-stream_url", event.target.dataset.stream_url);
                            
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

        						}).catch((err) => {
        							console.error("internet-radio: caught error in delete items handler: ", err);
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
					    if(this.debug){
                            console.log("internet radio debug: play button event: ", event);
                        }
                        //console.log(event.path[2]);
                        
                        try{
                            const playing_items = document.querySelectorAll('.extension-internet-radio-item-playing');
                            for (var i = 0; i < playing_items.length; ++i) {
                                playing_items[i].classList.remove('extension-internet-radio-item-playing');
                            }
                            event.target.closest('.extension-internet-radio-item').classList.add('extension-internet-radio-item-playing');
                            this.view.querySelector('#extension-internet-radio-now-playing').innerText = "";
                        }
                        catch (err){
                            console.error('internet radio: caught error with play button: ', err);
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
							
						}).catch((err) => {
							console.error("internet-radio: caught play button: error: ", err);
						});
                        
                        
					});
                    
                    
                    // Pause buttons on item. (speaker icon)
					const pause_button = clone.querySelectorAll('.extension-internet-radio-pause-icon')[0];
					pause_button.addEventListener('click', (event) => {

						// Send new values to backend
						window.API.postJson(
							`/extensions/${this.id}/api/ajax`,
							{'action':'pause'}
						).then((body) => { 
							if(this.debug){
							    console.log("debug: pause reaction: ", body);
							}
                            console.log("debug: pause reaction: ", body);
                            if(body.state == 'ok'){
                                this.playing = false;
                                document.body.classList.remove('extension-internet-radio-playing');
                                event.path[2].classList.remove('extension-internet-radio-item-playing');
                                this.view.querySelector('#extension-internet-radio-now-playing').innerText = "";
                            }

						}).catch((err) => {
							console.error("internet-radio: caught pause button: error: ", err);
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
			catch (err) {
				// statements to handle any exceptions
				console.log("internet radoio: caught error in regenerate_items: ", err); // pass exception object to error handler
			}
		}
	
    
    
    
    
    
        play_audio_in_browser(url){
            //document.getElementById('extension-internet-radio-audio-player').src = url;
            //console.log("start audio");
			
			if(typeof url == 'string'){
				if(url.startsWith('https://') && window.location.protocol == 'http'){
					url = url.replace('https://','http://');
				}
				else if(url.startsWith('http://') && window.location.protocol == 'https'){
					url = url.replace('http://','https://');
				}
				
	            if(typeof this.view.audio_player == 'undefined'){
	                //console.log("audio player didn't exist yet? making it now");
	                this.view.audio_player = new Audio(url);
	            }else{
	                //console.log("feeding audio player new url: " + url);
	                this.view.audio_player.pause();
	                this.view.audio_player.src = url;
	            }
            
	            this.view.audio_player.play();
			}
            
            
        }
    
        stop_audio_in_browser(){
            //console.log("stop audio");
            this.view.audio_player.pause();
            this.view.audio_player.src = "";
            try{
                const preview_buttons = document.querySelectorAll('.extension-internet-radio-preview');
                for (var i = 0; i < preview_buttons.length; ++i) {
                    preview_buttons[i].dataset.playing = "false";
                }
            }
            catch(err){
                console.error("internet radio: caught error stopping radio audio preview in browser: ", err);
            }
            
        }
    
    
    
    
        /**
         * Ask a specified server for a list of all other server.
         */
        get_radiobrowser_base_urls() {
            return new Promise((resolve, reject)=>{
                var request = new XMLHttpRequest()
                // If you need https, please use the fixed server fr1.api.radio-browser.info for this request only
                request.open('GET', window.location.protocol + '://all.api.radio-browser.info/json/servers', true);
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


