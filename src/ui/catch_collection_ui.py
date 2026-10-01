"""Catch Collection page: add, filter, show and delete catches."""

from datetime import date

import streamlit as st

from .. import catch_repository


# ---------------------------------------------------------
# Add Catch Form
# ---------------------------------------------------------

def render_add_catch_form():

    with st.container(border=True):

        st.subheader("Add a new catch")

        with st.form("add_catch_form", border=False):

            name_col, location_col, bundesland_col = st.columns(3)

            with name_col:

                fish_name = st.text_input(
                    "Name / Species",
                    placeholder="e.g. Pike",
                )

            with location_col:

                location = st.text_input(
                    "Location",
                    placeholder="e.g. Lake Schwielowsee",
                )

            with bundesland_col:

                bundesland = st.selectbox(
                    "Bundesland",
                    [""] + catch_repository.BUNDESLAENDER,
                )

            date_col, weight_col, length_col = st.columns(3)

            with date_col:

                catch_date = st.date_input(
                    "Date",
                    value=date.today(),
                )

            with weight_col:

                weight = st.number_input(
                    "Weight (kg)",
                    min_value=0.0,
                    step=0.1,
                )

            with length_col:

                length = st.number_input(
                    "Length (cm)",
                    min_value=0.0,
                    step=1.0,
                )

            image_col, notes_col = st.columns(2)

            with image_col:

                image = st.file_uploader(
                    "Fish image",
                    type=["png", "jpg", "jpeg", "webp"],
                )

            with notes_col:

                notes = st.text_area(
                    "Notes",
                    placeholder="Optional notes about the catch...",
                )

            _, cancel_col, save_col = st.columns([3, 1, 1])

            with cancel_col:

                cancel = st.form_submit_button(
                    "Cancel",
                    width="stretch",
                )

            with save_col:

                save_catch = st.form_submit_button(
                    "Save Catch",
                    type="primary",
                    width="stretch",
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

        with st.form("filter_form", border=False):

            col1, col2, col3 = st.columns(3)

            with col1:

                species = st.text_input(
                    "Species contains",
                    value=active["species"],
                    placeholder="e.g. Pike",
                )

            with col2:

                bundesland_options = ["All"] + catch_repository.BUNDESLAENDER

                bundesland = st.selectbox(
                    "Bundesland",
                    bundesland_options,
                    index=bundesland_options.index(active["bundesland"] or "All"),
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

            _, reset_col, apply_col = st.columns([3, 1, 1])

            with reset_col:

                reset_filters = st.form_submit_button(
                    "Reset",
                    width="stretch",
                )

            with apply_col:

                apply_filters = st.form_submit_button(
                    "Apply Filter",
                    type="primary",
                    width="stretch",
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

    # The key gives the card a CSS class, see catch cards in styles.py.
    with st.container(border=True, key=f"catch_card_{catch['id']}"):

        if catch["image"]:
            st.image(catch["image"])

        st.markdown(f"#### {catch['name']}")

        catch_date = date.fromisoformat(catch["catch_date"]).strftime("%d.%m.%Y")
        details = [f":material/calendar_today: {catch_date}"]

        if catch["location"] or catch["bundesland"]:

            place = " · ".join(
                part
                for part in [catch["location"], catch["bundesland"]]
                if part
            )

            details.append(f":material/location_on: {place}")

        st.caption("  \n".join(details))

        measurements = []

        if catch["length"] > 0:
            measurements.append(f":green-badge[:material/straighten: {catch['length']:.0f} cm]")

        if catch["weight"] > 0:
            measurements.append(f":green-badge[:material/scale: {catch['weight']:.2f} kg]")

        if measurements:
            st.markdown(" ".join(measurements))

        if catch["notes"]:
            st.caption(catch["notes"])

        if st.button(
            "Delete",
            icon=":material/delete:",
            type="tertiary",
            key=f"delete_{catch['id']}",
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
        vertical_alignment="bottom",
    )

    with title_col:
        st.title("Catch Collection")
        st.caption("Keep track of the fish you have caught.")

    with filter_col:

        if st.button(
            "Filter •" if filters_active else "Filter",
            icon=":material/filter_list:",
            width="stretch",
        ):
            st.session_state.show_filter = not st.session_state.show_filter
            st.rerun()

    with add_col:

        if st.button(
            "Add Catch",
            icon=":material/add:",
            width="stretch",
            type="primary",
        ):
            st.session_state.show_add_catch = True

    if st.session_state.show_filter:
        render_filter_form()

    if st.session_state.show_add_catch:
        render_add_catch_form()

    catches = catch_repository.get_catches(**st.session_state.filters)

    if not catches:

        st.info(
            "No catches found. Add your first catch with the "
            "button above or adjust the filters.",
            icon=":material/info:",
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
