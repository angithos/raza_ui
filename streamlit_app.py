
import streamlit as st
import requests
import re
import base64

def get_image_base64(path):

    with open(path, "rb") as image_file:
        return base64.b64encode(
            image_file.read()
        ).decode()

ORIGIN_CITIES = [
    "Berlin",
    "Munich",
    "Hamburg",
    "Cologne"
]

DESTINATION_CITIES = [
    "Paris",
    "Amsterdam",
    "Tokyo",
    "Berlin"
]

ACCOMMODATION_TYPES = [
    "Hotel",
    "Hostel",
    "Eco-hotel",
    "Apartment"
]

SUSTAINABILITY_OPTIONS = [
    "High",
    "Medium",
    "Low"
]

ORIGIN_IMAGES = {
    "Berlin": "images/Berlin.jpg",
    "Munich": "images/Munich.jpg",
    "Hamburg": "images/Hamburg.jpg",
    "Cologne": "images/Cologne.jpg"
}

DESTINATION_IMAGES = {
    "Paris": "images/Paris.jpg",
    "Amsterdam": "images/Amsterdam.jpg",
    "Tokyo": "images/Tokyo.jpg",
    "Berlin": "images/Berlin.jpg"
}


def send_message_to_rasa(message, sender="streamlit_user"):

    try:
        response = requests.post(
            "http://localhost:5005/webhooks/rest/webhook",
            json={
                "sender": sender,
                "message": message
            },
            timeout=10
        )

        if response.status_code != 200:
            return [
                "Sorry, I couldn't connect to the travel assistant."
            ]

        data = response.json()

        return [
            item["text"]
            for item in data
            if "text" in item
        ]

    except requests.exceptions.RequestException:
        return [
            "Sorry, I couldn't connect to the travel assistant."
        ]


def send_button_message(message):

    st.session_state.messages.append(
        {
            "role": "user",
            "content": message
        }
    )

    responses = send_message_to_rasa(message)

    for response in responses:
        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": response
            }
        )

    st.rerun()


def is_recommendation_message(content):

    content_lower = content.lower()

    keywords = [
        "accommodation recommendations",
        "transport options",
        "approximate transport distance",
        "estimated co₂",
        "estimated co2",
        "co₂ values are approximate"
    ]

    return any(
        keyword in content_lower
        for keyword in keywords
    )


def parse_accommodation(content):

    pattern = (
        r"\d+\.\s*(.*?)\s+"
        r"Type:\s*(.*?)\s+"
        r"Price:\s*€([\d.]+)\/night\s+"
        r"CO₂:\s*([\d.]+)\s*kg\/night\s+"
        r"Sustainability:\s*([\d.]+)\/10"
    )

    match = re.search(pattern, content, re.IGNORECASE)

    if not match:
        return None

    return {
        "name": match.group(1).strip(),
        "type": match.group(2).strip(),
        "price": match.group(3),
        "co2": match.group(4),
        "sustainability": match.group(5)
    }


def parse_transport(content):

    pattern = (
        r"\d+[\.\)]\s*(.*?)\s+"
        r"Price:\s*€([\d.]+)\s+"
        r"Duration:\s*([\d.]+)\s*hours\s+"
        r"Estimated CO₂:\s*([\d.]+)\s*kg"
    )

    matches = re.findall(
        pattern,
        content,
        re.IGNORECASE
    )

    transports = []

    for match in matches:

        transports.append(
            {
                "mode": match[0].strip(),
                "price": match[1],
                "duration": match[2],
                "co2": match[3]
            }
        )

    return transports


def parse_emissions(content):

    distance_match = re.search(
        r"Approximate transport distance:\s*([\d.]+)\s*km",
        content,
        re.IGNORECASE
    )

    co2_match = re.search(
        r"Estimated CO₂e:\s*([\d.]+)\s*kg",
        content,
        re.IGNORECASE
    )

    if not distance_match or not co2_match:
        return None

    return {
        "distance": distance_match.group(1),
        "co2": co2_match.group(1)
    }


def display_recommendation_card(content):

    accommodation = parse_accommodation(content)
    transports = parse_transport(content)
    emissions = parse_emissions(content)

    if accommodation:

        st.markdown("### 🏨 Accommodation")

        with st.container(border=True):

            st.subheader(
                accommodation["name"]
            )

            st.caption(
                accommodation["type"].replace("_", " ").title()
            )

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric(
                    "Price",
                    f"€{accommodation['price']}/night"
                )

            with col2:
                st.metric(
                    "CO₂",
                    f"{accommodation['co2']} kg/night"
                )

            with col3:
                st.metric(
                    "Sustainability",
                    f"{accommodation['sustainability']}/10"
                )

        return

    if emissions:

        with st.container(border=True):

            st.markdown("### 🌍 Journey emissions")

            col1, col2 = st.columns(2)

            with col1:
                st.metric(
                    "Distance",
                    f"{emissions['distance']} km"
                )

            with col2:
                st.metric(
                    "Estimated CO₂e",
                    f"{emissions['co2']} kg"
                )

        return

    if transports:

        st.markdown("### 🚆 Transport options")

        cols = st.columns(len(transports))

        for i, transport in enumerate(transports):

            with cols[i]:

                with st.container(border=True):

                    mode = transport["mode"]

                    if "bus" in mode.lower():
                        icon = "🚌"
                    elif "train" in mode.lower():
                        icon = "🚆"
                    elif "flight" in mode.lower():
                        icon = "✈️"
                    else:
                        icon = "🚍"

                    st.markdown(
                        f"### {icon} {mode}"
                    )

                    st.metric(
                        "Price",
                        f"€{transport['price']}"
                    )

                    st.write(
                        f"⏱️ **Duration:** "
                        f"{transport['duration']} hours"
                    )

                    st.write(
                        f"🌱 **CO₂:** "
                        f"{transport['co2']} kg"
                    )

        return


def display_message(message):

    content = message["content"]

    if message["role"] == "assistant" and is_recommendation_message(content):

        display_recommendation_card(content)

    else:

        with st.chat_message(message["role"]):
            st.write(content)

def city_card(city, image_path, key):

    image_base64 = get_image_base64(image_path)

    st.markdown(
        f"""
        <div class="city-card">
            <img
                src="data:image/jpeg;base64,{image_base64}"
                class="city-card-image"
            >
        </div>
        """,
        unsafe_allow_html=True
    )

    if st.button(
        city,
        key=key,
        use_container_width=True
    ):
        send_button_message(city)

st.set_page_config(
    page_title="EcoTravel Assistant",
    page_icon="🌱",
    layout="wide"
)
st.markdown(
    """
    <style>

    .city-card {
        width: 100%;
        overflow: hidden;
        border-radius: 12px 12px 0 0;
    }

    .city-card .city-card-image {
        width: 100% !important;
        height: 210px !important;
        max-width: none !important;
        object-fit: cover !important;
        object-position: center !important;
        display: block !important;
    }

    </style>
    """,
    unsafe_allow_html=True
)

st.title("🌱 EcoTravel Assistant")
st.caption("Sustainable travel planning assistant")


if "messages" not in st.session_state:

    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "Hello! 👋 I'm your sustainable travel assistant. "
                "I can help you find accommodation and transport "
                "options based on your preferences."
            )
        }
    ]


if "trip_started" not in st.session_state:
    st.session_state.trip_started = False


for message in st.session_state.messages:

    display_message(message)


if st.session_state.messages:

    last_message = st.session_state.messages[-1]

    if last_message["role"] == "assistant":

        question = last_message["content"].lower()

        if (
            "where are you travelling from" in question
            or "where are you traveling from" in question
            or "departure city" in question
        ):

            st.write("Suggested departure cities:")

            cols = st.columns(len(ORIGIN_CITIES))

            for i, city in enumerate(ORIGIN_CITIES):

                with cols[i]:
                    city_card(
                        city,
                        ORIGIN_IMAGES[city],
                        f"origin_{city}"
                    )
                    

            other_origin = st.text_input(
                "Or enter another departure city",
                key="other_origin",
                placeholder="e.g. Frankfurt"
            )

            if st.button(
                "Use departure city",
                key="use_origin",
                use_container_width=True
            ):

                if other_origin.strip():
                    send_button_message(
                        other_origin.strip()
                    )

        elif (
            "where would you like to travel" in question
            or "where would you like to go" in question
            or "destination" in question
        ):

            st.write("Suggested destinations:")

            cols = st.columns(len(DESTINATION_CITIES))

            for i, city in enumerate(DESTINATION_CITIES):

                with cols[i]:

                    city_card(
                        city,
                        DESTINATION_IMAGES[city],
                        f"origin_{city}"
                    )

            other_destination = st.text_input(
                "Or enter another destination",
                key="other_destination",
                placeholder="e.g. Rome"
            )

            if st.button(
                "Use destination",
                key="use_destination",
                use_container_width=True
            ):

                if other_destination.strip():
                    send_button_message(
                        other_destination.strip()
                    )

        elif (
            "date" in question
            or "when" in question
            or "travel on" in question
        ):

            st.write("Choose your travel date:")

            selected_date = st.date_input(
                "Travel date",
                key="travel_date_picker"
            )

            if st.button(
                "Use this date",
                key="use_date",
                use_container_width=True
            ):

                send_button_message(
                    selected_date.strftime("%d %B %Y")
                )

        elif (
            "type of accommodation" in question
            or "type of accomodation" in question
            or "accommodation would you prefer" in question
            or "accomodation would you prefer" in question
        ):

            st.write("Choose your accommodation type:")

            cols = st.columns(
                len(ACCOMMODATION_TYPES)
            )

            for i, accommodation in enumerate(
                ACCOMMODATION_TYPES
            ):

                with cols[i]:

                    if st.button(
                        accommodation,
                        key=f"accommodation_{accommodation}",
                        use_container_width=True
                    ):
                        send_button_message(
                            accommodation
                        )

        elif (
            "how important is sustainability" in question
            or "sustainability for you" in question
            or "sustainability preference" in question
        ):

            st.write(
                "Choose your sustainability preference:"
            )

            cols = st.columns(
                len(SUSTAINABILITY_OPTIONS)
            )

            for i, option in enumerate(
                SUSTAINABILITY_OPTIONS
            ):

                with cols[i]:

                    if st.button(
                        option,
                        key=f"sustainability_{option}",
                        use_container_width=True
                    ):
                        send_button_message(
                            option
                        )


if not st.session_state.trip_started:

    if st.button(
        "🌍 Start a trip",
        key="start_trip",
        use_container_width=True
    ):

        st.session_state.trip_started = True

        send_button_message(
            "I want to plan a trip"
        )


user_message = st.chat_input(
    "Type your message...",
    key="chat_input"
)


if user_message:

    st.session_state.messages.append(
        {
            "role": "user",
            "content": user_message
        }
    )

    responses = send_message_to_rasa(
        user_message
    )

    for response in responses:

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": response
            }
        )

    st.rerun()

