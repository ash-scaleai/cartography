import math

import pytest

from cartography.graph.anomaly_detection import AnomalyAlert
from cartography.graph.anomaly_detection import create_anomaly_alert
from cartography.graph.anomaly_detection import is_anomalous


class TestIsAnomalous:
    def test_empty_history(self):
        anomalous, reason = is_anomalous(100, [])
        assert anomalous is False
        assert reason == ""

    def test_single_entry_history(self):
        anomalous, reason = is_anomalous(100, [90])
        assert anomalous is False
        assert reason == ""

    def test_normal_count_within_threshold(self):
        # history mean=100, std_dev ~= 0 for all same values
        # but let's use varying values
        history = [98, 102, 100, 99, 101]
        # mean = 100, std_dev ~ 1.41
        # count=103 -> deviation = 3/1.41 ~ 2.12, just above 2
        # count=102 -> deviation = 2/1.41 ~ 1.41, below 2
        anomalous, reason = is_anomalous(102, history)
        assert anomalous is False

    def test_anomalous_count_above_threshold(self):
        history = [100, 100, 100, 100, 100, 102, 98, 101, 99, 100]
        # mean = 100, std_dev ~ 1.0
        # count=110 -> deviation = 10/1.0 = 10.0, way above 2
        anomalous, reason = is_anomalous(110, history)
        assert anomalous is True
        assert "110" in reason
        assert "std devs" in reason

    def test_anomalous_count_below_average(self):
        history = [100, 100, 100, 100, 100, 102, 98, 101, 99, 100]
        # count=90 -> deviation = 10/1.0 = 10.0
        anomalous, reason = is_anomalous(90, history)
        assert anomalous is True

    def test_custom_threshold(self):
        history = [100, 100, 100, 100, 100, 102, 98, 101, 99, 100]
        # mean=100, std~1.0, count=103, deviation=3.0
        # With threshold=2: anomalous. With threshold=4: not anomalous.
        anomalous_strict, _ = is_anomalous(103, history, std_dev_threshold=2.0)
        assert anomalous_strict is True

        anomalous_loose, _ = is_anomalous(103, history, std_dev_threshold=4.0)
        assert anomalous_loose is False

    def test_zero_std_dev_same_count(self):
        history = [100, 100, 100, 100, 100]
        # std_dev = 0, current matches -> not anomalous
        anomalous, reason = is_anomalous(100, history)
        assert anomalous is False
        assert reason == ""

    def test_zero_std_dev_different_count(self):
        history = [100, 100, 100, 100, 100]
        # std_dev = 0, current differs -> anomalous
        anomalous, reason = is_anomalous(101, history)
        assert anomalous is True
        assert "std_dev=0" in reason

    def test_large_deviation(self):
        history = [1000, 1000, 1000, 1000, 1000]
        anomalous, reason = is_anomalous(0, history)
        assert anomalous is True


class TestCreateAnomalyAlert:
    def test_returns_none_when_not_anomalous(self):
        history = [100, 100, 100, 100, 100]
        alert = create_anomaly_alert("test_module", 100, history)
        assert alert is None

    def test_returns_alert_when_anomalous(self):
        history = [100, 100, 100, 102, 98, 101, 99, 100, 100, 100]
        alert = create_anomaly_alert("test_module", 200, history)
        assert alert is not None
        assert isinstance(alert, AnomalyAlert)
        assert alert.module_name == "test_module"
        assert alert.current_count == 200
        assert alert.rolling_avg == 100.0
        assert alert.deviation > 2.0

    def test_returns_none_with_insufficient_history(self):
        alert = create_anomaly_alert("test_module", 100, [50])
        assert alert is None

    def test_alert_fields(self):
        history = [100, 100, 100, 102, 98, 101, 99, 100, 100, 100]
        alert = create_anomaly_alert("my_module", 200, history)
        assert alert is not None
        assert alert.module_name == "my_module"
        assert alert.current_count == 200
        assert isinstance(alert.message, str)
        assert len(alert.message) > 0
        assert alert.std_dev > 0
