from obswebsocket import obsws, requests
import sys

# Configuration
host = "localhost"
port = 4455  # Default port
password = "fV6udMhQbZZ84qAK"  # Set this if you have one

# Connect to OBS
ws = obsws(host, port, password)
ws.connect()

# Get the list of scenes
scenes = ws.call(requests.GetSceneList()).getScenes()

# Reverse the order of scenes
scenes.reverse()

# Get the scene index from command line argument
try:
    scene_index = int(sys.argv[1])
except (IndexError, ValueError):
    print("Please provide a valid scene index.")
    sys.exit(1)

# Validate the index
if scene_index < 0 or scene_index >= len(scenes):
    print("Scene index out of range.")
    sys.exit(1)

# Get the scene name from the index
scene_name = scenes[scene_index]['sceneName']

# Switch to the selected scene
ws.call(requests.SetCurrentProgramScene(sceneName=scene_name))

# Disconnect
ws.disconnect()