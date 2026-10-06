from rasa_sdk import Action
from dotenv import load_dotenv
from rasa_sdk.events import SlotSet, ActiveLoop
import os


load_dotenv()

CLIMATIQ_API_KEY = os.getenv("CLIMATIQ_API_KEY")

print("Climatiq key loaded:", bool(CLIMATIQ_API_KEY))

import requests



ACCOMMODATIONS = [
    # Berlin
    {
        "name": "Green Berlin Hotel",
        "type": "eco_hotel",
        "location": "Berlin",
        "price": 90,
        "co2_per_night": 5,
        "sustainability_score": 9
    },
    {
        "name": "Urban Hostel Berlin",
        "type": "hostel",
        "location": "Berlin",
        "price": 35,
        "co2_per_night": 8,
        "sustainability_score": 7
    },
    {
        "name": "Spree Eco-Apartment",
        "type": "apartment",
        "location": "Berlin",
        "price": 110,
        "co2_per_night": 4,
        "sustainability_score": 10
    },

    # Paris
    {
        "name": "Paris Eco Stay",
        "type": "eco_hotel",
        "location": "Paris",
        "price": 100,
        "co2_per_night": 6,
        "sustainability_score": 9
    },
    {
        "name": "Paris Central Hostel",
        "type": "hostel",
        "location": "Paris",
        "price": 40,
        "co2_per_night": 9,
        "sustainability_score": 7
    },
    {
        "name": "Seine Eco Apartment",
        "type": "apartment",
        "location": "Paris",
        "price": 120,
        "co2_per_night": 5,
        "sustainability_score": 10
    },

    # Amsterdam
    {
        "name": "Amsterdam Green Hotel",
        "type": "eco_hotel",
        "location": "Amsterdam",
        "price": 95,
        "co2_per_night": 5,
        "sustainability_score": 9
    },
    {
        "name": "Canal Hostel Amsterdam",
        "type": "hostel",
        "location": "Amsterdam",
        "price": 38,
        "co2_per_night": 8,
        "sustainability_score": 7
    },
    {
        "name": "Amsterdam Eco Apartment",
        "type": "apartment",
        "location": "Amsterdam",
        "price": 115,
        "co2_per_night": 4,
        "sustainability_score": 10
    },

    # Tokyo
    {
        "name": "Tokyo Eco Hotel",
        "type": "eco_hotel",
        "location": "Tokyo",
        "price": 95,
        "co2_per_night": 6,
        "sustainability_score": 9
    },
    {
        "name": "Tokyo Central Hostel",
        "type": "hostel",
        "location": "Tokyo",
        "price": 40,
        "co2_per_night": 8,
        "sustainability_score": 7
    },
    {
        "name": "Tokyo Green Apartment",
        "type": "apartment",
        "location": "Tokyo",
        "price": 115,
        "co2_per_night": 4,
        "sustainability_score": 10
    }
]

TRANSPORTS = [
    {
        "mode": "Intercity Train",
        "type": "train",
        "price": 60,
        "co2_kg": 12,
        "duration_hours": 4.5
    },
    {
        "mode": "Electric Long-Distance Bus",
        "type": "bus",
        "price": 25,
        "co2_kg": 18,
        "duration_hours": 7.0
    },
    {
        "mode": "Domestic Flight",
        "type": "flight",
        "price": 110,
        "co2_kg": 130,
        "duration_hours": 1.0
    }
]


ACTIVITIES = [

    # Berlin
    {
        "name": "Guided Bicycle City Tour",
        "location": "Berlin",
        "type": "tour",
        "price": 25,
        "co2": 0,
        "sustainability_score": 10
    },
    {
        "name": "Museum Island Pass",
        "location": "Berlin",
        "type": "culture",
        "price": 20,
        "co2": 1,
        "sustainability_score": 8
    },
    {
        "name": "Electric Boat Rental on the Spree",
        "location": "Berlin",
        "type": "leisure",
        "price": 45,
        "co2": 3,
        "sustainability_score": 7
    },

    # Paris
    {
        "name": "Paris Bicycle Tour",
        "location": "Paris",
        "type": "tour",
        "price": 25,
        "co2": 0,
        "sustainability_score": 10
    },
    {
        "name": "Louvre Museum Visit",
        "location": "Paris",
        "type": "culture",
        "price": 22,
        "co2": 1,
        "sustainability_score": 8
    },
    {
        "name": "Seine Electric Boat Tour",
        "location": "Paris",
        "type": "leisure",
        "price": 40,
        "co2": 3,
        "sustainability_score": 7
    },

    # Amsterdam
    {
        "name": "Amsterdam Bicycle Tour",
        "location": "Amsterdam",
        "type": "tour",
        "price": 20,
        "co2": 0,
        "sustainability_score": 10
    },
    {
        "name": "Rijksmuseum Visit",
        "location": "Amsterdam",
        "type": "culture",
        "price": 25,
        "co2": 1,
        "sustainability_score": 8
    },
    {
        "name": "Electric Canal Cruise",
        "location": "Amsterdam",
        "type": "leisure",
        "price": 35,
        "co2": 3,
        "sustainability_score": 8
    }
]
DISTANCES = {
    ("Berlin", "Paris"): 878,
    ("Berlin", "Amsterdam"): 577,
    ("Berlin", "Tokyo"): 8915,
    ("Paris", "Amsterdam"): 430,
    ("Paris", "Tokyo"): 9710,
    ("Amsterdam", "Tokyo"): 9330,
}


def get_distance(origin, destination):

    distance = DISTANCES.get((origin, destination))

    if distance is None:
        distance = DISTANCES.get((destination, origin))

    return distance


def calculate_emissions(distance_km):

    response = requests.post(
        "https://api.climatiq.io/data/v1/estimate",
        headers={
            "Authorization": f"Bearer {CLIMATIQ_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "emission_factor": {
                "id": "8a8900d7-9e7e-41e2-9310-a68dece95afc"
            },
            "parameters": {
                "distance": distance_km
            }
        }
    )

    if response.status_code != 200:
        print("Climatiq error:", response.text)
        return None

    data = response.json()

    return data["co2e"]


def calculate_trip_emissions(origin, destination):

    distance_km = get_distance(origin, destination)

    if distance_km is None:
        return None, None

    emissions = calculate_emissions(distance_km)

    return distance_km, emissions

class ActionExtractTripSlots(Action):

    def name(self):
        return "action_extract_trip_slots"

    def run(self, dispatcher, tracker, domain):

        events = []

        text = tracker.latest_message.get("text", "").strip()
        text_lower = text.lower()

        requested_slot = tracker.get_slot("requested_slot")

        # --------------------------------------------------
        # Full trip input: "from X to Y"
        # --------------------------------------------------

        if "from " in text_lower and " to " in text_lower:

            from_part = text_lower.split("from ", 1)[1]

            if " to " in from_part:

                origin_text = from_part.split(" to ", 1)[0].strip()
                destination_part = from_part.split(" to ", 1)[1]

                destination_text = destination_part

                if " on " in destination_text:
                    destination_text = destination_text.split(
                        " on ", 1
                    )[0].strip()

                elif " with " in destination_text:
                    destination_text = destination_text.split(
                        " with ", 1
                    )[0].strip()

                events.append(
                    SlotSet("origin", origin_text.title())
                )

                events.append(
                    SlotSet("destination", destination_text.title())
                )
        # --------------------------------------------------
        # Normal entity extraction
        # --------------------------------------------------
        elif "from " in text_lower and " to " not in text_lower:

            origin_text = text_lower.split("from ", 1)[1]

            if " instead" in origin_text:
                origin_text = origin_text.split(
                    " instead", 1
                )[0].strip()

            events.append(
                SlotSet("origin", origin_text.title())
            )
        for entity in tracker.latest_message.get("entities", []):

            entity_type = entity.get("entity")
            value = entity.get("value")

            # Don't overwrite origin/destination when we
            # already extracted them from "from X to Y".
            if entity_type == "origin":

                if not (
                    "from " in text_lower
                    and " to " in text_lower
                ):
                    events.append(
                        SlotSet("origin", value)
                    )

            elif entity_type == "destination":

                if not (
                    "from " in text_lower
                    and " to " not in text_lower
                ):
                    events.append(
                        SlotSet("destination", value)
                    )

            elif entity_type == "budget":

                events.append(
                    SlotSet(
                        "budget_max",
                        float(value)
                    )
                )

            elif entity_type == "date":

                events.append(
                    SlotSet("date", value)
                )

            elif entity_type == "accommodation_type":

                events.append(
                    SlotSet(
                        "accommodation_type",
                        value
                    )
                )

            elif entity_type == "sustainability_preference":

                events.append(
                    SlotSet(
                        "sustainability_preference",
                        value
                    )
                )

        dispatcher.utter_message(
            text="Trip details updated."
        )

        return events

class ActionFindTravelOptions(Action):

    def name(self):
        return "action_find_travel_options"

    def run(self, dispatcher, tracker, domain):

        # -------------------------------------------------
        # GET TRIP DETAILS
        # -------------------------------------------------

        origin = tracker.get_slot("origin")
        destination = tracker.get_slot("destination")
        date = tracker.get_slot("date")

        budget = tracker.get_slot("budget_max")

        sustainability = (
            tracker.get_slot("sustainability_preference")
            or "medium"
        )

        accommodation_type = tracker.get_slot(
            "accommodation_type"
        )

        # -------------------------------------------------
        # NORMALIZE ACCOMMODATION
        # -------------------------------------------------

        if accommodation_type:

            accommodation_text = accommodation_type.lower()

            if (
                "eco" in accommodation_text
                or "green" in accommodation_text
                or "environment" in accommodation_text
                or "sustainable" in accommodation_text
            ):
                accommodation_type = "eco_hotel"

            elif "hostel" in accommodation_text:
                accommodation_type = "hostel"

            elif "apartment" in accommodation_text:
                accommodation_type = "apartment"

            elif "hotel" in accommodation_text:
                accommodation_type = "hotel"

        # -------------------------------------------------
        # NORMALIZE SUSTAINABILITY
        # -------------------------------------------------

        if sustainability:

            sustainability_text = sustainability.lower()

            if (
                "most sustainable" in sustainability_text
                or "very important" in sustainability_text
                or sustainability_text == "high"
            ):
                sustainability = "high"

            elif (
                "balance" in sustainability_text
                or "reasonably sustainable" in sustainability_text
                or sustainability_text == "medium"
            ):
                sustainability = "medium"

            elif (
                "don't care" in sustainability_text
                or "not very important" in sustainability_text
                or sustainability_text == "low"
            ):
                sustainability = "low"

        print("===== RECOMMENDATION INPUT =====")
        print("Origin:", origin)
        print("Destination:", destination)
        print("Date:", date)
        print("Budget:", budget)
        print("Sustainability:", sustainability)
        print("Accommodation:", accommodation_type)
        print("================================")

        # -------------------------------------------------
        # 1. FILTER ACCOMMODATION BY DESTINATION
        # -------------------------------------------------

        accommodation_options = [
            accommodation
            for accommodation in ACCOMMODATIONS
            if accommodation["location"].lower()
            == destination.lower()
        ]

        # -------------------------------------------------
        # 2. FILTER BY ACCOMMODATION TYPE
        # -------------------------------------------------

        if accommodation_type:

            accommodation_options = [
                accommodation
                for accommodation in accommodation_options
                if accommodation["type"] == accommodation_type
            ]

        # -------------------------------------------------
        # 3. FILTER BY BUDGET
        # -------------------------------------------------

        if budget is not None:

            accommodation_options = [
                accommodation
                for accommodation in accommodation_options
                if accommodation["price"] <= float(budget)
            ]

        # -------------------------------------------------
        # 4. RANK ACCOMMODATION
        # -------------------------------------------------

        if sustainability == "high":

            accommodation_options.sort(
                key=lambda x: (
                    -x["sustainability_score"],
                    x["co2_per_night"],
                    x["price"]
                )
            )

        elif sustainability == "low":

            accommodation_options.sort(
                key=lambda x: (
                    x["price"],
                    x["co2_per_night"]
                )
            )

        else:

            # Medium = balance sustainability and price
            accommodation_options.sort(
                key=lambda x: (
                    -x["sustainability_score"],
                    x["price"]
                )
            )

        # -------------------------------------------------
        # 5. ACCOMMODATION RESPONSE
        # -------------------------------------------------

        if not accommodation_options:

            dispatcher.utter_message(
                text=(
                    f"I couldn't find accommodation matching "
                    f"your preferences in {destination}."
                )
            )

        else:

            recommended = accommodation_options[:3]

            response = (
                "Here are my accommodation recommendations:\n\n"
            )

            for index, accommodation in enumerate(
                recommended,
                start=1
            ):

                response += (
                    f"{index}. {accommodation['name']}\n"
                    f"   Type: {accommodation['type']}\n"
                    f"   Price: €{accommodation['price']}/night\n"
                    f"   CO₂: "
                    f"{accommodation['co2_per_night']} kg/night\n"
                    f"   Sustainability: "
                    f"{accommodation['sustainability_score']}/10\n\n"
                )

            dispatcher.utter_message(text=response)

        # -------------------------------------------------
        # 6. RANK TRANSPORT
        # -------------------------------------------------

        if sustainability == "high":

            transport_options = sorted(
                TRANSPORTS,
                key=lambda x: (
                    x["co2_kg"],
                    x["price"]
                )
            )

        elif sustainability == "low":

            transport_options = sorted(
                TRANSPORTS,
                key=lambda x: (
                    x["price"],
                    x["co2_kg"]
                )
            )

        else:

            # Medium = prioritize lower emissions,
            # with price used as a tie-breaker
            transport_options = sorted(
                TRANSPORTS,
                key=lambda x: (
                    x["co2_kg"],
                    x["price"]
                )
            )

        # Calculate approximate transport emissions
        distance_km, climatiq_co2 = calculate_trip_emissions(
            origin,
            destination
        )

        if climatiq_co2 is not None:
            dispatcher.utter_message(
                text=(
                    f"🌍 Approximate transport distance: "
                    f"{distance_km} km\n"
                    f"🌱 Estimated CO₂e: "
                    f"{climatiq_co2:.2f} kg"
                )
            )
        else:
            dispatcher.utter_message(
                text=(
                    "I couldn't calculate the transport emissions "
                    "for this route."
                )
            )

        # -------------------------------------------------
        # 7. TRANSPORT RESPONSE
        # -------------------------------------------------

        

        response = "🚆 Transport options:\n\n"

        for index, transport in enumerate(
            transport_options,
            start=1
        ):

            response += (
                f"{index}. {transport['mode']}\n"
                f"   Price: €{transport['price']}\n"
                f"   Duration: "
                f"{transport['duration_hours']} hours\n"
                f"   Estimated CO₂: "
                f"{transport['co2_kg']} kg\n\n"
            )

        response += (
            "CO₂ values are approximate estimates for "
            "demonstration purposes."
        )

        dispatcher.utter_message(text=response)

        return []   

class ActionHumanHandover(Action):

    def name(self):
        return "action_human_handover"

    def run(self, dispatcher, tracker, domain):

        origin = tracker.get_slot("origin")
        destination = tracker.get_slot("destination")
        date = tracker.get_slot("date")
        budget = tracker.get_slot("budget_max")
        accommodation = tracker.get_slot("accommodation_type")
        sustainability = tracker.get_slot(
            "sustainability_preference"
        )

        response = (
            "I'm connecting you with a travel advisor.\n\n"
            "Your trip details:\n"
            f"From: {origin}\n"
            f"To: {destination}\n"
            f"Date: {date}\n"
            f"Accommodation: {accommodation}\n"
            f"Budget: €{budget}/night\n"
            f"Sustainability preference: {sustainability}\n\n"
            "A travel advisor can continue from this information."
        )

        dispatcher.utter_message(text=response)

        return [ActiveLoop(None)]
    
class ActionRestartTrip(Action):

    def name(self):
        return "action_restart_trip"

    def run(self, dispatcher, tracker, domain):

        dispatcher.utter_message(
            text="Sure, let's start a new trip. I'll clear the previous trip details."
        )

        return [
            SlotSet("origin", None),
            SlotSet("destination", None),
            SlotSet("date", None),
            SlotSet("budget_max", None),
            SlotSet("accommodation_type", None),
            SlotSet("sustainability_preference", None),
            ActiveLoop("travel_form")
        ]
# class ActionClearSlots(Action):
#     def name(self):
#         return "action_clear_forms"
#     def run(self,dispatcher,domain,tsracker):
#         origin = tracker.get_slot("origin")
#         destination = tracker.get_slot("destination")
#         date = tracker.get_slot("date")
#         budget = tracker.get_slot("budget") or "No limit"
#         sustainability = tracker.get_slot("sustainability_preference") or "Default"
#         neworigin=tracker.

