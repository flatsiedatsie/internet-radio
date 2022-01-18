(function() {
	class InternetRadio extends window.Extension {
	    constructor() {
	      	super('internet-radio');
			//console.log("Adding internet-radio addon to menu");
      		
			this.addMenuEntry('Internet radio');
			
            
            var getCountryNames = new Intl.DisplayNames(['en'], {type: 'region'});
            console.log(getCountryNames);
            console.log(getCountryNames.of('AL'));  // "Albania"
            
			this.attempts = 0;

	      	this.content = '';
			this.item_elements = []; //['thing1','property1'];
			this.all_things;
			this.items_list = [];
			this.current_time = 0;
            
            this.stations = [];
            this.station = ""; // name of station that is currently playing (if the user has named the stream)
            
            this.entered_search_page = false;
            this.radio_browser_server = "";
            
            if(!this.entered_search_page){
                console.log("getting server address of radio browser server");
                this.entered_search_page = true;
                this.get_radiobrowser_base_url_random()
                .then((url) =>{
                    this.radio_browser_server = url;
                    console.log("url: " + url);
                });
            }
            
            
			fetch(`/extensions/${this.id}/views/content.html`)
	        .then((res) => res.text())
	        .then((text) => {
	         	this.content = text;
	  		 	if( document.location.href.endsWith("internet-radio") ){
					//console.log(document.location.href);
	  		  		this.show();
	  		  	}
	        })
	        .catch((e) => console.error('Failed to fetch content:', e));
            
            
            
            
            
            
	    }

		
		hide() {
			console.log("internet-radio hide called");
			try{
                this.audio_player.stop();
				clearInterval(this.interval);
				console.log("audio player stopped");
			}
			catch(e){
				console.log("no interval to clear? " + e);
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
				console.log("no interval to clear?: " + e);
			}
			
			const main_view = document.getElementById('extension-internet-radio-view');
			
			if(this.content == ''){
				return;
			}
			else{
				//document.getElementById('extension-internet-radio-view')#extension-internet-radio-view
				main_view.innerHTML = this.content;
			}
			
			this.audio_player = new Audio();
			//console.log("audio player: ", this.audio_player);

			const list = document.getElementById('extension-internet-radio-list');
		
			const pre = document.getElementById('extension-internet-radio-response-data');
			//const text_input_field = document.getElementById('extension-internet-radio-text-input-field');
			//const text_response_container = document.getElementById('extension-internet-radio-text-response-container');
			//const text_response_field = document.getElementById('extension-internet-radio-text-response-field');
			//text_response_container.style.display = 'none';
			
            
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
			
            
            // Easter egg: add custom station
            
			document.getElementById('extension-internet-radio-title').addEventListener('click', (event) => {
				//console.log("send button clicked");
                if(confirm("Would you like to add a custom radio station?")){
                    const new_url = prompt('Please provide the URL of the stream');
                    const new_name = prompt('Please give this station a name');
                    
                    if(new_name != "" && new_url.startsWith('http')){
    					// Send new values to backend
    					window.API.postJson(
    						`/extensions/${this.id}/api/ajax`,
    						{'action':'add', 'name':new_name, 'stream_url':new_url}
    					).then((body) => { 
    						console.log("add item reaction: ", body);
                            if(body.state = 'ok'){
                                alert("The station has been added. Refresh the page to see it.");
                            }else{
                                alert("Error: could not add station");
                            }
    					}).catch((e) => {
    						console.log("internet-radio: error in add items handler: ", e);
    						//pre.innerText = "Could not delete that station";
                            alert("Error: could not add station");
    					});
                    }
                    else{
                        alert("That didn't seem right. Make sure the stream starts with http, and that you provided a name");
                    }
			
					
                }
				
			});
            
			
            document.getElementById('extension-internet-radio-add-button').addEventListener('click', (event) => {
                //console.log("add button clicked");
                //document.getElementById('extension-internet-radio-add-button').style.display = 'none';
                document.getElementById('extension-internet-radio-search-page').style.display = 'block';
                document.getElementById('extension-internet-radio-stations-page').style.display = 'none';
                //document.getElementById('extension-internet-radio-back-button').style.display = 'block';
                
                if(!this.entered_search_page){
                    //console.log("getting server address of radio browser server");
                    this.entered_search_page = true;
                    this.get_radiobrowser_base_url_random()
                    .then((url) =>{
                        this.radio_browser_server = url;
                        console.log("radiobrowser.info url: " + url);
                    });
                }
                
			});
				
                
            document.getElementById('extension-internet-radio-back-button').addEventListener('click', (event) => {
                console.log("back button clicked");
                //document.getElementById('extension-internet-radio-add-button').style.display = 'block';
                document.getElementById('extension-internet-radio-search-page').style.display = 'none';
                document.getElementById('extension-internet-radio-stations-page').style.display = 'block';
                
                this.get_init_data();
			});
            
            
            document.getElementById('extension-internet-radio-toggle-button').addEventListener('click', (event) => {
                console.log("top-right stop button clicked");
                
		        window.API.postJson(
		          `/extensions/${this.id}/api/ajax`,
                    {'action':'toggle'}

		        ).then((body) => {
					console.log("Toggle result:");
					console.log(body);
                    if(typeof body.playing != 'undefined'){
                        if(body.playing){
                            document.getElementById('extension-internet-radio-content').classList.add('extension-internet-radio-playing');
                        }
                        else{
                            document.getElementById('extension-internet-radio-content').classList.remove('extension-internet-radio-playing');
                        }
                    }
				
		        }).catch((e) => {
		  			console.log("Error toggling radio: " + e.toString());
		        });	
                
                

			});
            
            
        
		    
		    
			// TABS
            /*
			document.getElementById('extension-internet-radio-tab-button-timers').addEventListener('click', (event) => {
				//console.log(event);
				document.getElementById('extension-internet-radio-content').classList = ['extension-internet-radio-show-tab-timers'];
			});
			document.getElementById('extension-internet-radio-tab-button-satellites').addEventListener('click', (event) => {
				document.getElementById('extension-internet-radio-content').classList = ['extension-internet-radio-show-tab-satellites'];
			});
			document.getElementById('extension-internet-radio-tab-button-tutorial').addEventListener('click', (event) => {
				document.getElementById('extension-internet-radio-content').classList = ['extension-internet-radio-show-tab-tutorial'];
			});
            */
            
			this.interval = setInterval(() => {
				
                const now_playing_element = document.getElementById('extension-internet-radio-now-playing');
                try{
    		        window.API.postJson(
    		          `/extensions/${this.id}/api/ajax`,
                        {'action':'poll'}

    		        ).then((body) => {
                        console.log(body);
                        if(typeof body.playing != 'undefined'){
                            if(body.playing){
                                this.playing = true;
                                document.getElementById('extension-internet-radio-content').classList.add('extension-internet-radio-playing');
                            }
                            else{
                                document.getElementById('extension-internet-radio-content').classList.remove('extension-internet-radio-playing');
                                this.playing = false;
                                now_playing_element.innerText = '';
                            }
                            document.getElementById('extension-internet-radio-toggle-button').classList.remove('hidden');
                        }
                        
                        if(typeof body.now_playing != 'undefined'){
                            if(body.now_playing != 'Advertisement'){
                                
                            }else{
                                now_playing_element.innerText = body.now_playing;
                            }
                            
                        }
                        
                    
    		        }).catch((e) => {
    		  			console.log("Error polling: " + e.toString());
    		        });
                    
                }
                catch(e){
                    console.log("Error doing poll: ", e);
                }
				
			}, 2000);
            
            
            this.get_init_data();
            
            
		}
		
	
        get_init_data(){
			try{
				//pre.innerText = "";
				
		  		// Init
		        window.API.postJson(
		          `/extensions/${this.id}/api/ajax`,
                    {'action':'init'}

		        ).then((body) => {
					console.log("Init API result:");
					console.log(body);
                    
                    this.station = body.station;
                    this.playing = body.playing;
                    
                    this.regenerate_items(body.stations);
                    
                    if(typeof body.debug != 'undefined'){
                        if(body.debug){
                            this.debug = body.debug;
                            document.getElementById('extension-internet-radio-debug-warning').style.display = 'block';
                        }
                    }
					
				
		        }).catch((e) => {
		  			console.log("Error getting InternetRadio init data: " + e.toString());
					pre.innerText = "Error getting initial InternetRadio data: " + e.toString();
		        });	

				
			}
			catch(e){
				console.log("Error in init: " + e);
			}
        }
    
    
	
        //
        //  SEARCH
        //
        
		send_search(){
            
			var text = document.getElementById('extension-internet-radio-search-field').value;
			//console.log(text);
			if(text == ""){
				text == "FIP";
			}
			
			console.log("Sending text command");
			
            var search_data = {'name':text};
            
            const countrycode = document.getElementById('extension-internet-radio-countries-dropdown').value;
            console.log("country code: " + countrycode);
            if(countrycode != 'ALL'){
                search_data['countrycode'] = countrycode;
            }
            
            var items = [];
            if (search_data.name) {
                items.push('name=' + encodeURIComponent(search_data.name));
            }
            if (search_data.countrycode) {
                items.push('countrycode=' + encodeURIComponent(search_data.countrycode));
            }
            if (search_data.state) {
                items.push('state=' + encodeURIComponent(search_data.state));
            }
            if (search_data.tag) {
                items.push('tag=' + encodeURIComponent(search_data.tag));
            }
            items.push('limit=' + encodeURIComponent('20'));
            const api_path = this.radio_browser_server + '/json/stations/search?' + items.join('&');

            console.log("api_path = ", api_path);

            this.radio_search(api_path).then((found_stations) =>{
                console.log("search result: ", found_stations);
                this.regenerate_items(found_stations, "search");
            });


            //get_radiobrowser_server_config(url)
            //.then((config) =>{
            //    console.log("got config: ", config);
            //});
            
		}
        
        
        
        
    
	
		//
		//  REGENERATE ITEMS
		//
	
		regenerate_items(items, page){
			try {
				console.log("regenerating. items: ", items);
		
				const pre = document.getElementById('extension-internet-radio-response-data');
				
				const original = document.getElementById('extension-internet-radio-original-item');
			    //console.log("original: ", original);
                
                if(typeof items == 'undefined'){
                    items = this.stations;
                }
			
				items.sort((a, b) => (a.name > b.name) ? 1 : -1) // sort alphabetically
				
                var list = document.getElementById('extension-internet-radio-stations-list');
                
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
                        if(typeof items[item].tags != "undefined"){
                            const tags_array = items[item].tags.split(",");
                            console.log(' tags_array: ' +  tags_array);
                            const tags_container = clone.getElementsByClassName("extension-internet-radio-item-tags")[0]
                            for (var i = 0; i < tags_array.length; i++) {
            					if(tags_array[i].length > 2){
                                    var s = document.createElement("span");
                					s.classList.add('extension-internet-radio-tag');                
                					var t = document.createTextNode(tags_array[i]);
                					s.appendChild(t);        
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
                            
                            const new_name = prompt('Please give this station a name');
                            const new_url = event.target.dataset.stream_url;
                            
    						var target = event.currentTarget;
    						var parent3 = target.parentElement.parentElement.parentElement;
    						parent3.classList.add("extension-internet-radio-item-added");
    						//var parent4 = parent3.parentElement;
    						//parent4.removeChild(parent3);
					
    						// Send new values to backend
    						window.API.postJson(
    							`/extensions/${this.id}/api/ajax`,
    							{'action':'add', 'name':new_name, 'stream_url':new_url}
    						).then((body) => { 
    							console.log("add item reaction: ", body);

    						}).catch((e) => {
    							console.log("internet-radio: error in add items handler: ", e);
    							//pre.innerText = "Could not delete that station";
    						});
					
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
        							console.log("delete item reaction: ", body);
                                    if(body.state == 'ok'){
                                        parent4.removeChild(parent3);
                                    }

        						}).catch((e) => {
        							console.log("internet-radio: error in delete items handler: ", e);
        							pre.innerText = "Could not delete that station"
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
                        console.log("playing: ", playing);
                        if(playing == "true"){
                            console.log("should stop audio");
                            this.stop_audio_in_browser();
                            //preview_button.setAttribute('data-playing', false);
                        }
                        else{
                            const preview_buttons = document.querySelectorAll('.extension-internet-radio-preview');
                            console.log("preview_buttons.length: " + preview_buttons.length);
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
					    console.log("event: ", event);
                        console.log(event.path[2]);
                        
                        const playing_items = document.querySelectorAll('.extension-internet-radio-item-playing');
                        for (var i = 0; i < playing_items.length; ++i) {
                            playing_items[i].classList.remove('extension-internet-radio-item-playing');
                        }
                        event.path[2].classList.add('extension-internet-radio-item-playing');
                        document.getElementById('extension-internet-radio-now-playing').innerText = "";
                        
                        console.log("play");
                        const play_url = event.target.dataset.stream_url;
                        console.log("play_url: ", play_url);
                        
						// Send new values to backend
						window.API.postJson(
							`/extensions/${this.id}/api/ajax`,
							{'action':'play','stream_url': play_url}
						).then((body) => { 
							console.log("play reaction: ", body);

                            
                            play_button.setAttribute('data-playing', true);
                            

						}).catch((e) => {
							console.log("internet-radio: error in delete items handler");
							pre.innerText = "Could not delete that station"
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
			
			}
			catch (e) {
				// statements to handle any exceptions
				console.log("Error in regenerate_items: ", e); // pass exception object to error handler
			}
		}
	
    
    
    
    
    
        play_audio_in_browser(url){
            //document.getElementById('extension-internet-radio-audio-player').src = url;
            //console.log("start audio");
            
            if(typeof this.audio_player == 'undefined'){
                this.audio_player = new Audio(url);
            }else{
                this.audio_player.pause();
                this.audio_player.src = url;
            }
            
            this.audio_player.play();
        }
    
        stop_audio_in_browser(){
            //console.log("stop audio");
            this.audio_player.pause();
            this.audio_player.src = "";
            
            const preview_buttons = document.querySelectorAll('.extension-internet-radio-preview');
            for (var i = 0; i < preview_buttons.length; ++i) {
                preview_buttons[i].dataset.playing = "false";
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
    
    
    
    
    
    
    }

	new InternetRadio();
	
})();


