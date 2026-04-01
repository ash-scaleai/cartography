import logging
import math
from dataclasses import dataclass
from typing import List
from typing import Tuple

logger = logging.getLogger(__name__)

DEFAULT_ANOMALY_STD_DEVS = 2.0


@dataclass
class AnomalyAlert:
    """
    Details about a detected anomaly in record counts.

    Attributes:
        module_name: The module whose count is anomalous.
        current_count: The count that triggered the alert.
        rolling_avg: The rolling average from history.
        std_dev: The standard deviation from history.
        deviation: How many standard deviations the current count differs.
        message: Human-readable description of the anomaly.
    """

    module_name: str
    current_count: int
    rolling_avg: float
    std_dev: float
    deviation: float
    message: str


def is_anomalous(
    current_count: int,
    history: List[int],
    std_dev_threshold: float = DEFAULT_ANOMALY_STD_DEVS,
) -> Tuple[bool, str]:
    """
    Determine whether a record count is anomalous relative to history.

    A count is considered anomalous if it deviates more than std_dev_threshold
    standard deviations from the rolling average of the history.

    Args:
        current_count: The current record count to evaluate.
        history: List of previous record counts.
        std_dev_threshold: Number of standard deviations to use as the
            anomaly threshold. Defaults to 2.0.

    Returns:
        A tuple of (is_anomalous, reason_string). If not anomalous, the
        reason string is empty.
    """
    if len(history) < 2:
        return False, ""

    mean = sum(history) / len(history)
    variance = sum((x - mean) ** 2 for x in history) / len(history)
    std_dev = math.sqrt(variance)

    if std_dev == 0.0:
        # All historical values are the same
        if current_count != mean:
            reason = (
                f"Count {current_count} differs from constant historical value "
                f"{int(mean)} (std_dev=0, any change is anomalous)"
            )
            logger.warning(reason)
            return True, reason
        return False, ""

    deviation = abs(current_count - mean) / std_dev
    if deviation > std_dev_threshold:
        reason = (
            f"Count {current_count} deviates {deviation:.2f} std devs from "
            f"rolling avg {mean:.2f} (std_dev={std_dev:.2f}, "
            f"threshold={std_dev_threshold})"
        )
        logger.warning(reason)
        return True, reason

    return False, ""


def create_anomaly_alert(
    module_name: str,
    current_count: int,
    history: List[int],
    std_dev_threshold: float = DEFAULT_ANOMALY_STD_DEVS,
) -> AnomalyAlert | None:
    """
    Create an AnomalyAlert if the current count is anomalous.

    Args:
        module_name: The module being checked.
        current_count: The current record count.
        history: List of previous record counts.
        std_dev_threshold: Number of standard deviations threshold.

    Returns:
        An AnomalyAlert if anomalous, None otherwise.
    """
    anomalous, reason = is_anomalous(current_count, history, std_dev_threshold)
    if not anomalous:
        return None

    if len(history) < 2:
        return None

    mean = sum(history) / len(history)
    variance = sum((x - mean) ** 2 for x in history) / len(history)
    std_dev = math.sqrt(variance)
    deviation = abs(current_count - mean) / std_dev if std_dev > 0 else float("inf")

    return AnomalyAlert(
        module_name=module_name,
        current_count=current_count,
        rolling_avg=mean,
        std_dev=std_dev,
        deviation=deviation,
        message=reason,
    )
