import json
import requests
import os
from openai import OpenAI
from prompts import formatter_prompt, assistant_instructions

OPENAI_API_KEY = os.environ['OPENAI_API_KEY']
GOOGLE_CLOUD_API_KEY = os.environ['GOOGLE_CLOUD_API_KEY']
AIRTABLE_API_KEY = os.environ['AIRTABLE_API_KEY']
RENTCAST_API_KEY = os.environ['RENTCAST_API_KEY']

# Init OpenAI Client
client = OpenAI(api_key=OPENAI_API_KEY)


# Use GPT completion to extract most relevant data from rental estimates
def simplify_rental_estimates_data(rental_estimates_data):
  try:
    data_str = json.dumps(rental_estimates_data, indent=2)

    # Getting formatter prompt from "prompts.py" file
    system_prompt = formatter_prompt

    # Replace 'client' with your actual OpenAI client initialization.
    completion = client.chat.completions.create(
        model="gpt-4-1106-preview",
        messages=[{
            "role": "system",
            "content": system_prompt
        }, {
            "role":
            "user",
            "content":
            f"Here is some data, parse and format it exactly as shown in the example: {data_str}"
        }],
        temperature=0)

    simplified_data = json.loads(completion.choices[0].message.content)
    print("Simplified Data:", simplified_data)
    return simplified_data

  except Exception as e:
    print("Error simplifying data:", e)
    return None


# Get rent estimates data for coordinate from RentCast API
def get_rent_estimates(lat, lng, property_type):
  url = f"https://api.rentcast.io/v1/avm/rent/long-term?latitude={lat}&longitude={lng}&propertyType={property_type}&compCount=5"

  headers = {"accept": "application/json", "x-api-key": RENTCAST_API_KEY}
  response = requests.get(url, headers=headers)

  if response.status_code == 200:
    print("Rent estimates data retrieved successfully.")
    return response.json()
  else:
    print(f"Error getting solar data: {response.text}")


# Get coordidinates from address via Geocoding API
def get_coordinates(address):
  geocoding_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={GOOGLE_CLOUD_API_KEY}"
  response = requests.get(geocoding_url)
  if response.status_code == 200:
    location = response.json().get('results')[0].get('geometry').get(
        'location')
    print(f"Coordinates for {address}: {location}")
    return location['lat'], location['lng']
  else:
    print(f"Error getting coordinates: {response.text}")


# Get financial data for the address
def get_rental_estimates_for_address(address, property_type):
  lat, lng = get_coordinates(address)
  if not lat or not lng:
    return {"error": "Could not get coordinates for the address provided."}
  return get_rent_estimates(lat, lng, property_type)


# Main calculation function for rent estimate data output
def rent_estimate_calculations(address, property_type):
  print(
      f"Calculating rent estimate options for {address} with property type {property_type}."
  )

  estimates = get_rental_estimates_for_address(address, property_type)
  if "error" in estimates:
    print(estimates["error"])
    return estimates
  return simplify_rental_estimates_data(estimates)


# Create or load assistant
def create_assistant(client):
  assistant_file_path = 'rental_assistant.json'

  # If there is an rental_assistant.json file already, then load that assistant
  if os.path.exists(assistant_file_path):
    with open(assistant_file_path, 'r') as file:
      assistant_data = json.load(file)
      assistant_id = assistant_data['assistant_id']
      print("Loaded existing assistant ID.")
  else:
    # If no rental_assistant.json is present,
    # create a new assistant using the below specifications
    file = client.files.create(file=open("knowledge.docx", "rb"),
                               purpose='assistants')

    assistant = client.beta.assistants.create(
        # Getting assistant prompt from "rental_prompts.py" file,
        # edit on left panel if you want to change the prompt
        instructions=assistant_instructions,
        model="gpt-4-1106-preview",
        tools=[
            {
                "type": "retrieval"  # This adds the knowledge base as a tool
            },
            {
                "type": "function",  # This adds the rent calculator as a tool
                "function": {
                    "name": "rent_estimate_calculations",
                    "description":
                    "Returns a property rent estimate and comparable properties based on a given address and price in USD.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "address": {
                                "type":
                                "string",
                                "description":
                                "Address for calculating rent estimate options."
                            },
                            "property_type": {
                                "type":
                                "string",
                                "description":
                                "The type of the property (e.g. Apartment, Condo, Multi-Family)."
                            }
                        },
                        "required": ["address", "property_type"]
                    }
                }
            },
            {
                "type": "function",  # This adds the lead capture as a tool
                "function": {
                    "name": "create_lead",
                    "description":
                    "Capture lead details and save to Airtable.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Name of the lead."
                            },
                            "phone": {
                                "type": "string",
                                "description": "Phone number of the lead."
                            },
                            "address": {
                                "type": "string",
                                "description": "Address of the lead."
                            }
                        },
                        "required": ["name", "phone", "address"]
                    }
                }
            }
        ],
        file_ids=[file.id])

    # Create a new assistant.json file to load on future runs
    with open(assistant_file_path, 'w') as file:
      json.dump({'assistant_id': assistant.id}, file)
      print("Created a new assistant and saved the ID.")

    assistant_id = assistant.id

  return assistant_id
