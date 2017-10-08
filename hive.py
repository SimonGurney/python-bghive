import urllib.request
import json

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
    session_id = None
    events = None
    nodes = None
    heating_node = None
    water_node = None

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
        json = self.json_to_bytes(json)
        req = urllib.request.Request(url,data=json,headers=self.__headers)
        response = urllib.request.urlopen(req)
        return self.bytes_to_json(response.read()) 
    def make_get(self, api_path):
        url = self.build_url(api_path)
        req = urllib.request.Request(url,headers=self.__headers)
        req.get_method = lambda: 'GET'
        response = urllib.request.urlopen(req)
        return self.bytes_to_json(response.read()) 
    def make_put(self, api_element_list, json):
        url = self.build_url(api_element_list)
        json = self.json_to_bytes(json)
        req = urllib.request.Request(url,data=json,headers=self.__headers)
        req.get_method = lambda: 'PUT'
        response = urllib.request.urlopen(req)
        return self.bytes_to_json(response.read()) 
    def login_to_hive(self):
        if len(self.__headers) is 4:
            return
        print("logging in")
        hive_credentials = {"sessions":[{
            "username":self.__username,
            "password":self.__password
            }]
        }
        self.session = self.make_post(self.AUTH_API, hive_credentials)['sessions'][0]
        self.__headers.update({"X-Omnia-Access-Token":self.session['id']})
    def get_events(self):
        self.events = self.make_get(self.EVENT_API)['events']
    def get_nodes(self):
        if self.nodes is None:
            self.nodes = self.make_get(self.NODE_API)['nodes']
    def set_to_schedule(self,node):
        if node is None:
            print("node not provided, you could try and use get_nodes to identify the node id yourself and place it in the class definition")
        json = self.construct_json("node",{"activeScheduleLock":False})
        api_element_list = [self.NODE_API,node]
        for x in range(2): # Send twice as observed a bit of hit and miss
            self.make_put(api_element_list,json)
    def set_boost(self,node,duration = False,temp = False):
        if node is None:
            print("node not provided, you could try and use get_nodes to identify the node id yourself and place it in the class definition")
        if not duration:
            duration = self.DEFAULT_BOOST_DURATION
        params = {"activeHeatCoolMode":"BOOST","activeScheduleLock":True,"scheduleLockDuration":duration}
        if node == self.heating_node:
            if not temp:
                temp = self.DEFAULT_BOOST_TEMP
            params.update({"activeHeatTemperature":temp})
        json = self.construct_json("node",params)
        self.make_put([self.NODE_API,node],json)
    def find_water_node(self):
        if self.water_node is not None:
            return
        self.get_nodes()
        for node in self.nodes:
            if "supportsHotWater" in node["attributes"]:
                if node["attributes"]["supportsHotWater"]["reportedValue"] == True:
                    self.water_node = node["id"]
                    return
    def find_heating_node(self):
        if self.heating_node is not None:
            return
        self.get_nodes()
        for node in self.nodes:
            if "activeHeatTemperature" in node["attributes"]:
                self.heating_node = node["id"]
                return
    def find_nodes(self):
        self.find_water_node()
        self.find_heating_node()
    def __init__(self,username,password):
        self.__username = username
        self.__password = password
        self.login_to_hive()
        self.find_nodes()