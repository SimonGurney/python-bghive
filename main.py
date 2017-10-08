from hive import Hive

user = input("Username / Email:  ")
password = input("Password:  ")
h = Hive(user,password)

# Print all nodes - useful for finding the correct node although events are better
#h.get_nodes()
#for node in h.nodes:
#    print("Node id: %s, name: %s"%(node['id'],node['name']))
#    print(node)

# Print all events - useful for recreating a previous webgui action
#h.get_events()
#for event in h.events:
#    print(event)

# Some commands, h.water_node and h.heating_node should be populated during init, if it doesn't or you have more than one Hive
# in your account then you should set the relevant property and then call schedule/boost in the same way.
# This is because the method checks the nodeid against these stored properties to work out if a water or heating
# action needs to be submitted.
h.set_to_schedule(h.water_node)
#h.set_to_schedule(h.heating_node)
#h.set_boost(h.water_node)
#h.set_boost(h.heating_node)