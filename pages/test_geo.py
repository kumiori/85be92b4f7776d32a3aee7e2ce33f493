import streamlit as st

from infra.cryosphere_cracks import cryosphere_crack_points
from ui import cracks_globe_block

st.set_page_config(layout="wide")

st.title("Hello, we are mapping.")
st.markdown(
    """
We're excited to collaborate to explore and map the irreversible processes and behaviour of the cryosphere.

Our aim is to create an interactive and collaborative platform to map knowledge and bridge its gaps, foster
interdisciplinary connections, and deepen our understanding of ice behaviour.
"""
)
name = st.text_input(
    "`I'd love for us to get to know each other a bit better. Nice to meet you, I’m...`"
)

if name:
    st.success(f"Wonderful to have you onboard, {name}.")
    st.markdown("### A Few Things to Know Before We Get Started:")
    st.markdown(
        """
    - **Purpose**: This initiative focuses on mapping knowledge about ice behavior, processes, and fracture phenomena, emphasizing scientific collaboration and interdisciplinary engagement.
    - **Your Role**: Your input will help create a shared knowledge map, identify gaps in understanding, and foster meaningful exchanges between researchers and practitioners.
    - **Privacy**: All shared data and responses are for collaborative research purposes only and will be handled with the utmost confidentiality.
    """
    )
    agree = st.checkbox("Acknowledged", key="acknowledge")

    if agree:
        st.success("Great! Let's move forward and connect.")
    else:
        st.warning("Please acknowledge the guidelines to proceed.")

cracks_globe_block(
    cryosphere_crack_points(),
    height=820,
    key="test-geo-cracks",
    auto_rotate_speed=2.6,
)
