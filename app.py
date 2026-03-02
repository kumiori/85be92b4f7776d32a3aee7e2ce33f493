import streamlit as st

st.title("Ice Ice Baby")

st.write("Welcome to the app!")

name = st.text_input("Enter your name", "World")

if st.button("Say hello"):
    st.write(f"Hello, {name}!")
