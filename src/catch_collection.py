"""
Catch Collection page: add, filter, show and delete catches.
The data itself is stored in SQLite (see catch_repository.py).
"""

from datetime import date

import streamlit as st

from src import catch_repository


# ---------------------------------------------------------
# Add Catch Form
# ---------------------------------------------------------

def render_add_catch_form():

    with st.container(border=True):

        st.subheader("Add a new catch")

        with st.form("add_catch_form"):

            fish_name = st.text_input(
                "Name / Species",
                placeholder="e.g. Pike",
            )

            location_col, state_col = st.columns(2)

            with location_col:

                location = st.text_input(
                    "Location",
                    placeholder="e.g. Lake Schwielowsee",
                )

            with state_col:

                bundesland = st.selectbox(
                    "Bundesland",
                    [""] + catch_repository.BUNDESLAENDER,
                )

            col1, col2, col3 = st.columns(3)

            with col1:

                catch_date = st.date_input(
                    "Date",
                    value=date.today(),
                )

            with col2:

                weight = st.number_input(
                    "Weight (kg)",
                    min_value=0.0,
                    step=0.1,
                )

            with col3:

                length = st.number_input(
                    "Length (cm)",
                    min_value=0.0,
                    step=1.0,
                )

            image = st.file_uploader(
                "Fish image",
                type=["png", "jpg", "jpeg", "webp"],
            )

            notes = st.text_area(
                "Notes",
                placeholder="Optional notes about the catch...",
            )

            save_col, cancel_col = st.columns(2)

            with save_col:

                save_catch = st.form_submit_button(
                    "Save Catch",
                    type="primary",
                    use_container_width=True,
                )

            with cancel_col:

                cancel = st.form_submit_button(
                    "Cancel",
                    use_container_width=True,
                )

        # Cancel
        if cancel:
            st.session_state.show_add_catch = False
            st.rerun()

        # Save
        if save_catch:

            if not fish_name:
                st.warning(
                    "Please enter a name or fish species."
                )

            else:

                catch_repository.add_catch(
                    name=fish_name,
                    location=location,
                    bundesland=bundesland,
                    catch_date=catch_date,
                    weight=weight,
                    length=length,
                    notes=notes,
                    image=image.getvalue() if image else None,
                )

                st.session_state.show_add_catch = False

                st.rerun()


# ---------------------------------------------------------
# Filters
# ---------------------------------------------------------

DEFAULT_FILTERS = {
    "species": "",
    "bundesland": None,
    "date_from": None,
    "date_to": None,
    "min_length": 0.0,
    "min_weight": 0.0,
    "sort_by": "date_desc",
}

SORT_LABELS = {
    "date_desc": "Date (newest first)",
    "date_asc": "Date (oldest first)",
    "length_desc": "Length (longest first)",
    "weight_desc": "Weight (heaviest first)",
    "name_asc": "Name (A-Z)",
}


def render_filter_form():
    """
    Filter panel. The selected values are only applied to the
    collection when the user clicks "Apply Filter".
    """

    active = st.session_state.filters

    with st.container(border=True):

        st.subheader("Filter catches")

        with st.form("filter_form"):

            col1, col2, col3 = st.columns(3)

            with col1:

                species = st.text_input(
                    "Species contains",
                    value=active["species"],
                    placeholder="e.g. Pike",
                )

            with col2:

                bundesland = st.selectbox(
                    "Bundesland",
                    ["All"] + catch_repository.BUNDESLAENDER,
                    index=(
                        0
                        if active["bundesland"] is None
                        else catch_repository.BUNDESLAENDER.index(
                            active["bundesland"]
                        ) + 1
                    ),
                )

            with col3:

                sort_by = st.selectbox(
                    "Sort by",
                    list(SORT_LABELS),
                    index=list(SORT_LABELS).index(active["sort_by"]),
                    format_func=lambda option: SORT_LABELS[option],
                )

            col4, col5, col6, col7 = st.columns(4)

            with col4:

                date_from = st.date_input(
                    "From",
                    value=active["date_from"],
                )

            with col5:

                date_to = st.date_input(
                    "To",
                    value=active["date_to"],
                )

            with col6:

                min_length = st.number_input(
                    "Min. length (cm)",
                    min_value=0.0,
                    step=1.0,
                    value=active["min_length"],
                )

            with col7:

                min_weight = st.number_input(
                    "Min. weight (kg)",
                    min_value=0.0,
                    step=0.1,
                    value=active["min_weight"],
                )

            apply_col, reset_col = st.columns(2)

            with apply_col:

                apply_filters = st.form_submit_button(
                    "Apply Filter",
                    type="primary",
                    use_container_width=True,
                )

            with reset_col:

                reset_filters = st.form_submit_button(
                    "Reset",
                    use_container_width=True,
                )

        # Reset
        if reset_filters:
            st.session_state.filters = dict(DEFAULT_FILTERS)
            st.rerun()

        # Apply
        if apply_filters:

            st.session_state.filters = {
                "species": species,
                "bundesland": None if bundesland == "All" else bundesland,
                "date_from": date_from,
                "date_to": date_to,
                "min_length": min_length,
                "min_weight": min_weight,
                "sort_by": sort_by,
            }

            st.session_state.show_filter = False

            st.rerun()


# ---------------------------------------------------------
# Catch Cards
# ---------------------------------------------------------

def render_catch_card(catch):

    with st.container(border=True):

        if catch["image"]:
            st.image(catch["image"])

        st.subheader(catch["name"])

        if catch["location"] or catch["bundesland"]:

            place = " · ".join(
                part
                for part in [catch["location"], catch["bundesland"]]
                if part
            )

            st.write(f"📍 {place}")

        st.write(
            f"📅 {date.fromisoformat(catch['catch_date']).strftime('%d.%m.%Y')}"
        )

        if catch["length"] > 0:
            st.write(f"📏 {catch['length']:.0f} cm")

        if catch["weight"] > 0:
            st.write(f"⚖️ {catch['weight']:.2f} kg")

        if catch["notes"]:
            st.caption(catch["notes"])

        if st.button(
            "🗑️ Delete",
            key=f"delete_{catch['id']}",
            use_container_width=True,
        ):
            catch_repository.delete_catch(catch["id"])
            st.rerun()


# ---------------------------------------------------------
# Page
# ---------------------------------------------------------

def render_page():

    catch_repository.init_db()

    if "show_add_catch" not in st.session_state:
        st.session_state.show_add_catch = False

    if "show_filter" not in st.session_state:
        st.session_state.show_filter = False

    if "filters" not in st.session_state:
        st.session_state.filters = dict(DEFAULT_FILTERS)

    filters_active = st.session_state.filters != DEFAULT_FILTERS

    # Header
    title_col, filter_col, add_col = st.columns(
        [4, 1, 1],
        vertical_alignment="center",
    )

    with title_col:
        st.title("🐟 Catch Collection")
        st.caption("Keep track of the fish you have caught.")

    with filter_col:

        if st.button(
            "🔎 Filter •" if filters_active else "🔎 Filter",
            use_container_width=True,
        ):
            st.session_state.show_filter = not st.session_state.show_filter
            st.rerun()

    with add_col:

        if st.button(
            "➕ Add Catch",
            use_container_width=True,
            type="primary",
        ):
            st.session_state.show_add_catch = True

    if st.session_state.show_filter:
        render_filter_form()

    if st.session_state.show_add_catch:
        render_add_catch_form()

    catches = catch_repository.get_catches(**st.session_state.filters)

    st.divider()

    if not catches:

        st.info(
            "No catches found. Add your first catch with the "
            "button above or adjust the filters."
        )

        return

    st.caption(
        f"{len(catches)} catches"
        + (" (filtered)" if filters_active else "")
    )

    catches_per_row = 3

    for start_index in range(0, len(catches), catches_per_row):

        columns = st.columns(catches_per_row)

        current_catches = catches[
            start_index:start_index + catches_per_row
        ]

        for column, catch in zip(columns, current_catches):

            with column:
                render_catch_card(catch)
