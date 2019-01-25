import urllib.request # Use urlib to reduce dependancy requirement
import json
from time import sleep
from threading import Thread
import logging

logging.basicConfig(level=logging.DEBUG, format='%(levelname)5s %(thread)d %(funcName)15s() %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p')

class Hive:
    ENCODING = "utf-8"
    API_BASE_URL = "https://api-prod.bgchprod.info/omnia"
    AUTH_API = "auth/sessions"
    NODE_API = "nodes"
    EVENT_API = "events"
    DEFAULT_BOOST_DURATION = 120
    DEFAULT_BOOST_TEMP = 21.0
    __username = None
    __password = None
    __headers = {
    "Content-Type":"application/vnd.alertme.zoo-6.1+json",
    "Accept":"application/vnd.alertme.zoo-6.1+json",
    "X-Omnia-Client":"Python call"
    }
    session = None
    events = None
    nodes = None
    heating_node = None
    water_node = None
    thermostat_node = None
    active_lights_nodes = None
    active_plug_nodes = None

    def build_url(self,url_parts_ordered):
        buf = self.API_BASE_URL
        if isinstance(url_parts_ordered,str):
            url_parts_ordered = [url_parts_ordered]
        if isinstance(url_parts_ordered,list):
            for part in url_parts_ordered:
                buf = "%s/%s" %(buf,part.strip("/"))
        else:
            raise ValueError("Need a string or a list")
        return buf
    def construct_json(self, purpose, dict_of_parameters):
        purpose = purpose.lower()
        dict = {}
        for k,v in dict_of_parameters.items():
            dict.update({k:{"targetValue":v}})
        if purpose == "node":
            j = {"nodes":[{"attributes":dict}]}
        return j
    def bytes_to_json(self,bytes):
        return json.loads(bytes.decode(self.ENCODING))
    def json_to_bytes(self,dict):
        return json.dumps(dict).encode(self.ENCODING)
    def make_post(self, api_path, json):
        url = self.build_url(api_path)
        logging.debug("Making POST with url: %s" % url)
        json = self.json_to_bytes(json)
        logging.debug("POSTing some JSON: %s" % json)
        req = urllib.request.Request(url,data=json,headers=self.__headers)
        response = urllib.request.urlopen(req)
        logging.debug("Got a response: %s" % response)
        return self.bytes_to_json(response.read()) 
    def make_get(self, api_path):
        url = self.build_url(api_path)
        logging.debug("Making GET with url: %s" % url)
        req = urllib.request.Request(url,headers=self.__headers)
        req.get_method = lambda: 'GET'
        response = urllib.request.urlopen(req)
        logging.debug("Got a response: %s" % response)
        return self.bytes_to_json(response.read()) 
    def make_put(self, api_element_list, json):
        url = self.build_url(api_element_list)
        logging.debug("Making PUT with url: %s" % url)
        json = self.json_to_bytes(json)
        logging.debug("PUTing some JSON: %s" % json)
        req = urllib.request.Request(url,data=json,headers=self.__headers)
        req.get_method = lambda: 'PUT'
        response = urllib.request.urlopen(req)
        logging.debug("Got a response: %s" % response)
        return self.bytes_to_json(response.read()) 
    def login_to_hive(self):
        #  What is this for?
        if len(self.__headers) is 4:
            return
        hive_credentials = {"sessions":[{
            "username":self.__username,
            "password":self.__password
            }]
        }
        logging.info("Logging into Hive with username: %s" % self.__username)
        self.session = self.make_post(self.AUTH_API, hive_credentials)['sessions'][0]
        logging.debug("Logged in with session %s" % self.session['id'])
        self.__headers.update({"X-Omnia-Access-Token":self.session['id']})
        logging.debug("Headers now: %s" % self.__headers)
    def check_session(self):
        try:
            self.make_get(["auth","sessions",self.session['id']])
            logging.debug("Session is valid")
            return True
        except:
            logging.debug("Session is not valid")
            return False
    def keepalive(self):
        while True:
            sleep(5 * 60)
            if not self.check_session():
                if "X-Omnia-Access-Token" in self.__headers:
                    logging.debug("Removing session token from headers.  Token: %s" % self.__headers.pop("X-Omnia-Access-Token"))
                self.login_to_hive()
    def get_events(self):
        self.events = self.make_get(self.EVENT_API)['events']
    def get_nodes(self):
        if self.nodes is None:
            self.nodes = self.make_get(self.NODE_API)['nodes']
    def set_to_schedule(self,node):
        json = self.construct_json("node",{"activeScheduleLock":False})
        api_element_list = [self.NODE_API,node.id]
        self.make_put(api_element_list,json)
    def set_boost(self,node,duration = False,temp = False):
        if not duration:
            duration = self.DEFAULT_BOOST_DURATION
        params = {"activeHeatCoolMode":"BOOST","activeScheduleLock":True,"scheduleLockDuration":duration}
        if node == self.heating_node:
            if not temp:
                temp = self.DEFAULT_BOOST_TEMP
            params.update({"activeHeatTemperature":temp})
        json = self.construct_json("node",params)
        self.make_put([self.NODE_API,node.id],json)
    def find_thermostat_node(self):
        if self.thermostat_node is not None:
            return
        if self.water_node is None:
            self.find_water_node()
        for node in self.nodes:
            if node["id"] == self.water_node.parent_node_id:
                self.thermostat_node = Node(node)
                return
    def find_water_node(self):
        if self.water_node is not None:
            return
        self.get_nodes()
        for node in self.nodes:
            if "supportsHotWater" in node["attributes"]:
                if node["attributes"]["supportsHotWater"]["reportedValue"] == True:
                    self.water_node = WaterNode(node)
                    return
    def find_heating_node(self):
        if self.heating_node is not None:
            return
        self.get_nodes()
        if self.thermostat_node is None:
            self.find_thermostat_node()
        for node in self.nodes:
            if node["parentNodeId"] == self.thermostat_node.id:
                if "supportsHotWater" in node["attributes"]:
                    if node["attributes"]["supportsHotWater"]["reportedValue"] == False:
                        self.heating_node = HeatingNode(node)
    def find_active_light_nodes(self):
        if self.active_lights_nodes is not None:
            return
        self.get_nodes()
        for node in self.nodes:
            if 'attributes' in node and 'nodeType' in node['attributes'] and 'reportedValue' in node['attributes']['nodeType'] and node['attributes']['nodeType']['reportedValue'] == 'http://alertme.com/schema/json/node.class.colour.tunable.light.json#':
                if self.active_lights_nodes == None:
                    self.active_light_nodes = {}
                self.active_light_nodes.update({node['name']:ActiveLight(node)})#.append(ActiveLight(node))
        pass
    def find_active_plug_nodes(self):
        if self.active_plug_nodes is not None:
            return
        self.get_nodes()
        pass
    def find_nodes(self):
        self.find_water_node()
        self.find_heating_node()
        self.find_active_light_nodes()
        self.find_active_plug_nodes()
    def set_active_light_colour(self, node, colour):
        params = {"hsvSaturation":99,"hsvValue":100,"colourMode":"COLOUR","hsvHue":colour,"state":"ON"}
        json = self.construct_json("node",params)
        api_element_list = [self.NODE_API,node.id]
        self.make_put(api_element_list,json)
    def __init__(self,username,password):
        self.__username = username
        self.__password = password
        self.login_to_hive()
        self.find_nodes()
        Thread(target=self.keepalive).start()

class Node:
    id = None
    name = None
    node_type = None
    parent_node_id = None
    attributes = None
    def get_attribute(self, attribute):
        return self.attributes[attribute]['reportedValue']
    def refresh_attributes(self, hive):
        #for node in hive.make_get(hive.NODE_API)['nodes']:
        api_element_list = [hive.NODE_API,self.id]
        for node in hive.make_get(api_element_list)['nodes']:
            if node['id'] == self.id:
                self.__init__(node)
    def __init__(self, node):
        self.id = node['id']
        self.name = node['name']
        self.node_type = node['attributes']['nodeType']['reportedValue']
        self.parent_node_id = node['parentNodeId']
        self.attributes = node['attributes']
    def __repr__(self):
        return "\nid: %s \nnode type: %s\nparent_node_id = %s\n\n" %(self.id, self.node_type, self.parent_node_id)

class CentralHeatingNode(Node):
    active_schedule_lock = None
    schedule = None
    def __init__(self, node):
        super().__init__(node)
        self.schedule = self.get_attribute('schedule')
        self.active_schedule_lock = self.get_attribute('activeScheduleLock')

class HeatingNode(CentralHeatingNode):
    supports_hot_water = None
    def  __init__(self, node):
        super().__init__(node)
        self.supports_hot_water = self.get_attribute('supportsHotWater')

class WaterNode(CentralHeatingNode):
    supports_hot_water = None
    def  __init__(self, node):
        super().__init__(node)
        self.supports_hot_water = self.get_attribute('supportsHotWater')

class ActiveLight(Node):
    hue_blue = 240
    hue_red = 360
    hue_green = 100
    hue_purple = 280
    hue_yellow = 60
    hue_orange = 40
    colour_mode_colour = "COLOUR"
    colour_mode_white = "TUNABLE"
    state_on = "ON"
    state_off = "OFF"
    colour_brightness = None
    white_brightness = None
    colour_mode = None
    __colour_temperature = None
    __hue = None # Range 0 to 360
    __state = None
    maximum_white_temperature = None
    minimum_white_temperature = None
    boost_thread_kill_signal = False
    colour_cycle_interval = 0
    colour_cycle_kill_signal = False
    def set_colour(self, hive, colour, kill_colour_cycle=True, brightness = None):
        logging.debug("Entered set colour function with colour: %d, kill_colour_cycle: %s and brightness = %s" %(colour,kill_colour_cycle,brightness))
        if kill_colour_cycle:
            self.stop_colour_cycle()
        if brightness is None:
            self.refresh_attributes(hive)
            brightness = self.colour_brightness
        params = {"hsvSaturation":99,"hsvValue":brightness,"colourMode":self.colour_mode_colour,"hsvHue":colour}
        json = hive.construct_json("node",params)
        api_element_list = [hive.NODE_API,self.id]
        hive.make_put(api_element_list,json)
    def set_white(self, hive, temperature, brightness = None):
        if brightness is None:
            self.refresh_attributes(hive)
            brightness = self.white_brightness
        params = {"brightness":brightness,"colourMode":self.colour_mode_white,"colourTemperature":temperature}
        json = hive.construct_json("node",params)
        api_element_list = [hive.NODE_API,self.id]
        hive.make_put(api_element_list,json)
    def set_brightness(self, hive, brightness = 100):
        if self.colour_mode == self.colour_mode_colour:
            params = {"hsvValue":brightness}
        elif self.colour_mode == self.colour_mode_white:
            params = {"brightness":brightness}
        json = hive.construct_json("node",params)
        api_element_list = [hive.NODE_API,self.id]
        hive.make_put(api_element_list,json)
    def set_state(self, hive, state):
        logging.debug("Setting state  to %s" % state)
        params = {"state":state}
        json = hive.construct_json("node",params)
        api_element_list = [hive.NODE_API,self.id]
        hive.make_put(api_element_list,json)
    def stop_boost(self):
        logging.debug("Breaking the loop of any existing boost threads by setting boost thread kill flag to True")
        self.boost_thread_kill_signal = True
        sleep(0.2)
    def boost(self, hive, time_m):
        self.stop_boost()
        self.set_state(hive, self.state_on)
        logging.debug("Setting boost kill flag to False")
        self.boost_thread_kill_signal = False
        Thread(target=self._boost,args=(hive, time_m)).start()
    def _boost(self, hive, time_m):
        logging.debug("Entered boost thread with time of %2f minutes" % time_m)
        time_s = time_m * 60
        x = 0
        while ((x < time_s) and (self.boost_thread_kill_signal == False)):
            sleep(0.1)
            x = x + 0.1
        logging.debug("Broke out of boost loop.  x is %d and boost thread kill signal is %s" %(x, self.boost_thread_kill_signal))
        if self.boost_thread_kill_signal == True:
            logging.debug("Boost thread signal set to True so something request the end of the boost")
            sleep(0.5)
            if self.boost_thread_kill_signal == False:
                logging.debug("Boost thread signal back to False so must be yielding to another boost")
                return
            else:
                logging.debug("Boost thread signal still set to True so no new thread spawned, turning off light")
        else:
                logging.debug("Boost thread signal set to False so must have left boost based on time")
        self.set_state(hive, self.state_off)
    def colour_cycle(self, hive, interval_s = 3, starting_colour = None):
        logging.debug("Entered colour cycle with interval of %f and starting_colour of %s" %(interval_s, starting_colour))
        if starting_colour is None:
            self.refresh_attributes(hive)
            logging.debug("Setting starting colour to %d" % self.__hue)
            starting_colour = self.__hue
        self.stop_colour_cycle() #Kill before changing the interval in case its now shorter
        logging.debug("Setting colour cycle interval to %f" % interval_s)
        self.colour_cycle_interval = interval_s
        self.set_colour(hive, starting_colour)
        sleep(interval_s / 5)
#        self.set_state(hive,self.state_on)
        logging.debug("Setting colour cycle thread kill signal to False")
        self.colour_cycle_thread_kill_signal=False
        Thread(target=self._colour_cycle, args=(hive, starting_colour)).start()
    def _colour_cycle(self, hive, starting_colour):
        current_colour = float(starting_colour + 1)
        logging.debug("Entered colour cycle thread with current_colour = %4f" % current_colour)
        while((current_colour != starting_colour) & (self.colour_cycle_thread_kill_signal == False)):
            if current_colour > 360:
                current_colour = current_colour - 360
            if round(current_colour,1).is_integer(): # Dirty way of applying every 10 repetitions
                self.set_colour(hive, current_colour, False)
            sleep(self.colour_cycle_interval / 20)
            current_colour += 0.1
        logging.debug("Left colour cycle loop")
    def stop_colour_cycle(self):
        logging.debug("Stopping current colour cycle via colour cycle thread kill signal")
        self.colour_cycle_thread_kill_signal = True
        sleep(self.colour_cycle_interval / 10)
    def __init__(self, node):
        super().__init__(node)
        self.colour_brightness = self.get_attribute('hsvValue')
        self.white_brightness = self.get_attribute('brightness')
        self.colour_mode = self.get_attribute('colourMode')
        self.__colour_temperature = self.get_attribute('colourTemperature')
        self.__hue = self.get_attribute('hsvHue')
        #self.maximium_white_temperature = self.get_attribute('maxColourTemperature')
        #self.minimium_white_temperature = self.get_attribute('minColourTemperature')
        self.__state = self.get_attribute('state')

#print(h.active_light_nodes[0].state)
#print(h.active_light_nodes)
#h.active_light_nodes["Harrison’s"].set_colour(h, ActiveLight.hue_green)
#h.active_light_nodes["Harrison’s"].colour_cycle(h)
#sleep(10)
#h.active_light_nodes["Harrison’s"].stop_colour_cycle()
#h.active_light_nodes["Harrison’s"].colour_cycle(h)
#sleep(10)
#h.active_light_nodes["Harrison’s"].stop_colour_cycle()
#h.active_light_nodes["Harrison’s"].colour_cycle(h)
#sleep(2)
#h.active_light_nodes["Harrison’s"].refresh_attributes(h)
#h.active_light_nodes["Harrison’s"].set_brightness(h,20)
#h.get_events()
#print(h.events[0])
#print(h.events[1])
#print(h.events[2])
#print(h.events[3])
#print(h.events[4])
#print(h.events[5])