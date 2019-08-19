import logging
import os

from marshmallow import ValidationError

from cartography.driftdetect.reporter import report_drift
from cartography.driftdetect.serializers import ShortcutSchema
from cartography.driftdetect.serializers import StateSchema
from cartography.driftdetect.storage import FileSystem
from cartography.driftdetect.util import valid_directory

logger = logging.getLogger(__name__)


def run_drift_detection(config):
    try:
        if not valid_directory(config.query_directory):
            logger.error("Invalid Drift Detection Directory")
            return
        state_serializer = StateSchema()
        shortcut_serializer = ShortcutSchema()
        new_results, missing_results, end_state = detect_drift_from_fp(
            config.query_directory,
            FileSystem,
            state_serializer,
            shortcut_serializer,
            config.start_state,
            config.end_state,
        )
        report_drift(new_results, missing_results, end_state.name, end_state.properties)
    except ValidationError as err:
        msg = "Unable to create DriftStates from files {},{} for \n{} in directory {}.".format(
            config.start_state,
            config.end_state,
            err.messages,
            config.query_directory,
        )
        logger.exception(msg)
    except ValueError as err:
        msg = "Unable to create DriftStates from files {},{} for \n{} in directory {}.".format(
            config.start_state,
            config.end_state,
            err,
            config.query_directory,
        )
        logger.exception(msg)


def detect_drift_from_fp(query_directory, storage, state_serializer, shortcut_serializer, start_state_fp, end_state_fp):
    """
    Performs Drift Detection between two files.
    :param query_directory: The query directory.
    :param storage: The storage object.
    :param state_serializer: The serializer for states.
    :param shortcut_serializer: The serializer for shortcuts.
    :param start_state_fp: The start state filepath
    :param end_state_fp: The end state filepath
    :return: the new_results, missing_results, and end state
    """
    shortcut_data = storage.load(os.path.join(query_directory, "shortcut.json"))
    shortcut = shortcut_serializer.load(shortcut_data)
    start_state_data = storage.load(
        os.path.join(
            query_directory, shortcut.shortcuts.get(
                start_state_fp,
                start_state_fp,
            ),
        ),
    )
    start_state = state_serializer.load(start_state_data)
    end_state_data = storage.load(
        os.path.join(
            query_directory, shortcut.shortcuts.get(
                end_state_fp,
                end_state_fp,
            ),
        ),
    )
    end_state = state_serializer.load(end_state_data)
    new_results, missing_results = perform_drift_detection(start_state, end_state)
    return new_results, missing_results, end_state


def perform_drift_detection(start_state, end_state):
    """
    Returns differences (additions and missing results) between two States.

    :type start_state: State
    :param start_state: The earlier state chronologically to be compared to.
    :type end_state: State
    :param end_state: The later state chronologically to be compared to.
    :return: tuple of additions and subtractions between the end and start detector in the form of drift_info_detector
    pairs
    """
    if start_state.name != end_state.name:
        raise ValueError("State names do not match.")
    if start_state.validation_query != end_state.validation_query:
        raise ValueError("State queries do not match.")
    if start_state.properties != end_state.properties:
        raise ValueError("State properties do not match.")
    new_results = compare_states(start_state, end_state)
    missing_results = compare_states(end_state, start_state)
    return new_results, missing_results


def compare_states(start_state, end_state):
    """
    Helper function for comparing differences between two States.

    :type start_state: State
    :param start_state: The earlier state chronologically to be compared to.
    :type end_state: State
    :param end_state: The later state chronologically to be compared to.
    :return: list of tuples of differences between states in the form (dictionary, State object)
    """
    differences = []
    for result in end_state.results:
        if result in start_state.results:
            continue
        drift = []
        for field in result:
            value = field.split("|")
            if len(value) > 1:
                drift.append(value)
            else:
                drift.append(field)
        differences.append(drift)
    return differences