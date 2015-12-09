from collections import OrderedDict

from pytest import fixture

from yelp_kafka_tool.kafka_cluster_manager.cluster_info.util import _validate_assignment
from yelp_kafka_tool.kafka_cluster_manager.cluster_info.util import _validate_format
from yelp_kafka_tool.kafka_cluster_manager.cluster_info.util import _validate_plan_base
from yelp_kafka_tool.kafka_cluster_manager.cluster_info.util import extract_actions_unique_topics
from yelp_kafka_tool.kafka_cluster_manager.cluster_info.util import get_assignment_map
from yelp_kafka_tool.kafka_cluster_manager.cluster_info.util import get_plan
from yelp_kafka_tool.kafka_cluster_manager.cluster_info.util import get_reduced_proposed_plan
from yelp_kafka_tool.kafka_cluster_manager.cluster_info.util import validate_plan


@fixture
def orig_assignment():
    return OrderedDict([
        ((u'T1', 1), [2, 1]),
        ((u'T0', 0), [0, 1]),
        ((u'T0', 1), [1, 2]),
        ((u'T1', 0), [0, 1]),
        ((u'T2', 0), [3, 1]),
    ])


@fixture
def new_assignment():
    return OrderedDict([
        ((u'T0', 0), [2, 0]),
        ((u'T1', 1), [2, 3]),
        ((u'T0', 1), [2, 1]),
        ((u'T1', 0), [0, 1]),
        ((u'T2', 0), [1, 3]),
    ])


def test_reduced_proposed_plan_no_change(orig_assignment):
    # Provide same assignment
    proposed_assignment = get_reduced_proposed_plan(
        original_assignment=orig_assignment,
        new_assignment=orig_assignment,
        max_partition_movements=1,
        max_leader_only_changes=1,
    )

    # Verify no proposed plan
    assert proposed_assignment == {}


def test_extract_actions_unique_topics_limited_actions():
    proposed_assignment = [
        ((u'T0', 0), [2, 0], 1),
        ((u'T0', 1), [2, 1], 1),
        ((u'T1', 0), [0, 1], 1),
        ((u'T2', 0), [1, 3], 1),
    ]
    red_proposed_assignment = extract_actions_unique_topics(
        proposed_assignment,
        3,
    )

    assert len(red_proposed_assignment) == 3
    topics = [action[0][0] for action in red_proposed_assignment]
    # Verify that all actions have unique topic
    assert sorted(topics) == sorted(list(set(topics)))


def test_extract_actions_partition_movement_no_action():
    # In case max-allowed partition-movements is less than replication-factor
    # there is a possibility it will never converge
    proposed_assignment = [
        ((u'T0', 0), [2, 0], 2),
        ((u'T0', 1), [2, 1], 2),
        ((u'T1', 0), [0, 1], 2),
        ((u'T2', 0), [1, 3], 2),
    ]
    red_proposed_assignment = extract_actions_unique_topics(
        proposed_assignment,
        1,
    )

    # All actions have minimum of 2 movements
    # so reduced proposed-plan is empty
    assert red_proposed_assignment == []


def test_extract_actions_partition_movements_only():
    proposed_assignment = [
        ((u'T0', 0), [2, 0], 2),
        ((u'T0', 1), [2, 1], 1),
        ((u'T1', 0), [0, 1], 2),
        ((u'T2', 0), [1, 3], 1),
    ]
    red_proposed_assignment = extract_actions_unique_topics(
        proposed_assignment,
        10,
    )

    # Total movements as in proposed-plan is 6 (2+1+2+1)
    # max partition-movements allowed is 10, so all 6 partition-movements
    # allowed
    assert len(red_proposed_assignment) == 4


def test_extract_actions_no_movements():
    proposed_assignment = [
        ((u'T0', 0), [2, 0], 2),
        ((u'T0', 1), [2, 1], 1),
        ((u'T1', 0), [0, 1], 2),
        ((u'T2', 0), [1, 3], 1),
    ]
    red_proposed_assignment = extract_actions_unique_topics(
        proposed_assignment,
        0,
    )

    # Total movements as in proposed-plan is 6 (2+1+2+1)
    # max partition-movements allowed is 10, so all 6 partition-movements
    # allowed
    assert red_proposed_assignment == []


def test_extract_actions_unique_topics_limited_actions_2():
    proposed_assignment = [
        ((u'T0', 0), [2, 0], 1),
        ((u'T0', 1), [2, 1], 1),
        ((u'T1', 0), [0, 1], 1),
        ((u'T1', 1), [0, 1], 1),
        ((u'T2', 0), [1, 3], 1),
    ]
    red_proposed_assignment = extract_actions_unique_topics(
        proposed_assignment,
        4,
    )

    total_movements = sum([
        action[2]
        for action in proposed_assignment
        if action[0:2] in red_proposed_assignment
    ])
    assert total_movements == 4
    topics = [action[0][0] for action in red_proposed_assignment]
    # Verify that only topic is non-unique
    assert len(sorted(topics)) - 1 == len(sorted(list(set(topics))))


def test_extract_actions_unique_topics_all_actions():
    proposed_assignment = [
        ((u'T0', 0), [2, 0], 1),
        ((u'T1', 1), [2, 3], 2),
        ((u'T0', 1), [2, 1], 2),
        ((u'T1', 0), [0, 1], 1),
        ((u'T2', 0), [1, 3], 1),
    ]
    red_proposed_assignment = extract_actions_unique_topics(
        proposed_assignment,
        7,
    )

    # assert final assignment is same as original assignment
    expected_assignment = [action[0:2] for action in proposed_assignment]
    assert sorted(red_proposed_assignment) == sorted(expected_assignment)


def test_extract_actions_unique_topics_some_actions():
    # Complex case
    # Total proposed-movements: 2*4 + 1 = 10
    # Max allowed movements: 5
    # Total actions in proposed_assignment: 5
    # Expected: Final assignment should have all 3 actions
    # all 3 unique topics
    proposed_assignment = [
        ((u'T0', 0), [2, 0], 2),
        ((u'T1', 1), [2, 3], 2),
        ((u'T0', 1), [2, 1], 2),
        ((u'T1', 0), [0, 1], 2),
        ((u'T2', 0), [1, 3], 1),
    ]
    red_proposed_assignment = extract_actions_unique_topics(
        proposed_assignment,
        5,
    )

    assert len(red_proposed_assignment) == 3
    assert ((u'T2', 0), [1, 3]) in red_proposed_assignment
    # Verify only 1 action for T1 and T2
    assert sum(1 for action in red_proposed_assignment if action[0][0] == 'T1') == 1
    assert sum(1 for action in red_proposed_assignment if action[0][0] == 'T2') == 1


def test_extract_actions_final_movements_lesser_than_max():
    # Complex case
    # Total proposed-movements: 2*4 + 1 = 10
    # Max allowed movements: 6
    # Total actions in proposed_assignment: 5
    # Expected: Final assignment should have all 3 actions
    # all 3 unique topics
    # Also, final movements will be 5 instead of max-allowed 6
    # This is done, since keeping the uniqueness of topic is more important than
    # getting max-possible partition-movements.
    proposed_assignment = [
        ((u'T0', 0), [2, 0], 2),
        ((u'T1', 1), [2, 3], 2),
        ((u'T0', 1), [2, 1], 2),
        ((u'T1', 0), [0, 1], 2),
        ((u'T2', 0), [1, 3], 1),
    ]
    red_proposed_assignment = extract_actions_unique_topics(
        proposed_assignment,
        6,
    )

    assert len(red_proposed_assignment) == 3
    assert ((u'T2', 0), [1, 3]) in red_proposed_assignment
    # Verify only 1 action for T1 and T2
    assert sum(1 for action in red_proposed_assignment if action[0][0] == 'T1') == 1
    assert sum(1 for action in red_proposed_assignment if action[0][0] == 'T2') == 1
    # Verify final movements will be 5 instead of max allowed 6
    assert sum(
        action[2]
        for action in proposed_assignment
        if action[0:2] in red_proposed_assignment
    ) == 5


def test_extract_actions_unique_topics_lesser_actions():
    proposed_assignment = [
        ((u'T0', 0), [2, 0], 2),
        ((u'T0', 1), [2, 1], 2),
        ((u'T1', 0), [0, 1], 2),
        ((u'T2', 0), [1, 3], 2),
    ]
    red_proposed_assignment = extract_actions_unique_topics(
        proposed_assignment,
        3,
    )

    assert len(red_proposed_assignment) == 1
    topics = [action[0][0] for action in red_proposed_assignment]
    # Verify that all actions have unique topic
    assert sorted(topics) == sorted(list(set(topics)))


def test_reduced_proposed_plan_max_invalid(orig_assignment, new_assignment):
    # Provide less than max_changes parameter
    proposed_assignment = get_reduced_proposed_plan(
        orig_assignment,
        new_assignment,
        max_partition_movements=0,
        max_leader_only_changes=0,
    )

    # Verify no proposed plan
    assert proposed_assignment == {}

    proposed_assignment = get_reduced_proposed_plan(
        orig_assignment,
        new_assignment,
        max_partition_movements=-1,
        max_leader_only_changes=0,
    )

    # Verify no proposed plan
    assert proposed_assignment == {}

    proposed_assignment = get_reduced_proposed_plan(
        orig_assignment,
        new_assignment,
        max_partition_movements=0,
        max_leader_only_changes=-1,
    )

    # Verify no proposed plan
    assert proposed_assignment == {}


def test_reduced_proposed_plan_empty(orig_assignment):
    # Provide empty assignment
    proposed_assignment = get_reduced_proposed_plan(
        orig_assignment,
        new_assignment=None,
        max_partition_movements=1,
        max_leader_only_changes=1,
    )

    # Verify no proposed plan
    assert proposed_assignment == {}

    proposed_assignment = get_reduced_proposed_plan(
        original_assignment=None,
        new_assignment=orig_assignment,
        max_partition_movements=1,
        max_leader_only_changes=1,
    )

    # Verify no proposed plan
    assert proposed_assignment == {}


def test_reduced_proposed_plan(orig_assignment, new_assignment):
    # Provide same assignment
    result = get_reduced_proposed_plan(
        orig_assignment,
        new_assignment,
        max_partition_movements=2,
        max_leader_only_changes=0,
    )

    # Verify that result is not None
    red_proposed_assignment = dict((ele[0], ele[1]) for ele in result[1])
    proposed_plan = get_plan(red_proposed_assignment)
    # Verify length of proposed-plan actions as 2
    assert len(proposed_plan['partitions']) == 2

    result = get_reduced_proposed_plan(
        orig_assignment,
        new_assignment,
        max_partition_movements=5,
        max_leader_only_changes=5,
    )

    red_proposed_assignment = dict((ele[0], ele[1]) for ele in result[1])
    proposed_plan = get_plan(red_proposed_assignment)
    # Verify no proposed plan less than max-changes
    assert len(proposed_plan['partitions']) == 4
    # Verify that proposed-plan is first change in sorted order of
    # partition-name
    assert sorted(proposed_plan['partitions']) == sorted([
        {'partition': 0, 'topic': u'T0', 'replicas': [2, 0]},
        {'partition': 1, 'topic': u'T0', 'replicas': [2, 1]},
        {'partition': 1, 'topic': u'T1', 'replicas': [2, 3]},
        {'partition': 0, 'topic': u'T2', 'replicas': [1, 3]}
    ])


def test_assignment_map():
    assignment_json = {u'version': 1, u'partitions': [
        {u'replicas': [0, 1, 2], u'topic': u'T3', u'partition': 0},
        {u'replicas': [0, 3], u'topic': u'T0', u'partition': 1},
    ]}
    expected_map = OrderedDict(sorted([
        (('T3', 0), [0, 1, 2]),
        (('T0', 1), [0, 3]),
    ]))

    assert expected_map == get_assignment_map(assignment_json)

# Tests for validation of plan


def test_validate_format():
    assignment = {
        "version": 1,
        "partitions": [
            {"partition": 0, "topic": 't1', "replicas": [0, 1]},
            {"partition": 1, "topic": 't1', "replicas": [1, 2]},
            {"partition": 0, "topic": 't2', "replicas": [1, 2]}
        ]
    }

    # Verify correct format
    assert _validate_format(assignment) is True


def test_validate_format_version_absent():
    assignment = {
        "partitions":
        [{"partition": 0, "topic": 't1', "replicas": [0, 1, 2]}]
    }

    # 'version' key missing: Verify Validation failed
    assert _validate_format(assignment) is False


def test_validate_format_invalid_key():
    # Invalid key "cluster"
    assignment = {
        "cluster": "invalid_key",
        "partitions":
        [{"partition": 0, "topic": 't1', "replicas": [0, 1, 2]}]
    }

    # Verify validation failed
    assert _validate_format(assignment) is False


def test_validate_format_partitions_absent():
    assignment = {"version": 1}

    # 'partitions' key missing: Verify Validation failed
    assert _validate_format(assignment) is False


def test_validate_format_version_wrong():
    # Invalid version 2
    assignment = {
        "version": 2,
        "partitions":
        [{"partition": 0, "topic": 't1', "replicas": [0, 1, 2]}]
    }

    # Verify validation failed
    assert _validate_format(assignment) is False


def test_validate_format_empty():
    # Empty assignment
    assignment = {}

    # Verify validation failed
    assert _validate_format(assignment) is False


def test_validate_format_partitions_empty():
    # Empty partitions-list
    assignment = {
        "version": 1,
        "partitions": []
    }

    # Verify validation failed
    assert _validate_format(assignment) is False


def test_validate_format_invalid_key_partition():
    # Invalid/unwanted key 'isr'
    assignment = {
        "version": 1,
        "partitions":
        [
            {"topic": 't1', "replicas": [0, 1, 2]},
            {"isr": [0, 1, 2], "partition": 0, "topic": 't2', "replicas": [0, 1, 2]}
        ]
    }

    # Verify validation failed
    assert _validate_format(assignment) is False


def test_validate_format_missing_key_partition():
    # 'partition' key missing in partitions
    assignment = {
        "version": 1,
        "partitions":
        [
            {"topic": 't1', "replicas": [0, 1, 2]},
            {"partition": 0, "topic": 't2', "replicas": [0, 1, 2]}
        ]
    }

    # Verify validation failed
    assert _validate_format(assignment) is False


def test_validate_format_missing_key_topic():
    # 'topic' key missing in partitions
    assignment = {
        "version": 1,
        "partitions":
        [
            {"partition": 0, "replicas": [0, 1, 2]},
            {"partition": 0, "topic": 't2', "replicas": [0, 1, 2]}
        ]
    }

    # Verify validation failed
    assert _validate_format(assignment) is False


def test_validate_format_missing_key_replicas():
    # 'replicas' key missing in partitions
    assignment = {
        "version": 1,
        "partitions":
        [
            {"partition": 0, "topic": 't1'},
            {"partition": 0, "topic": 't2', "replicas": [0, 1, 2]}
        ]
    }

    # Verify validation failed
    assert _validate_format(assignment) is False


def test_validate_format_invalid_type_partitions():
    # 'partitions' is not list
    assignment = {
        "version": 1,
        "partitions": {"partition": 0, "topic": 't2', "replicas": [0, 1, 2]}
    }

    # Verify validation failed
    assert _validate_format(assignment) is False


def test_validate_format_invalid_type_partition():
    # partition-id is not int
    assignment = {
        "version": 1,
        "partitions": [{"partition": '0', "topic": 't2', "replicas": [0, 1, 2]}]
    }

    # Verify validation failed
    assert _validate_format(assignment) is False


def test_validate_format_invalid_type_topic():
    # topic-id is not string
    assignment = {
        "version": 1,
        "partitions": [{"partition": 0, "topic": 2, "replicas": [0, 1, 2]}]
    }

    # Verify validation failed
    assert _validate_format(assignment) is False


def test_validate_format_invalid_type_replicas():
    # replicas is not list
    assignment = {
        "version": 1,
        "partitions": [{"partition": 0, "topic": 't1', "replicas": 0}]
    }

    # Verify validation failed
    assert _validate_format(assignment) is False


def test_validate_format_invalid_type_replica_brokers():
    # replica-brokers are not int
    assignment = {
        "version": 1,
        "partitions": [{"partition": 0, "topic": 't1', "replicas": ['0', 1]}]
    }

    # Verify validation failed
    assert _validate_format(assignment) is False


def test_validate_format_replica_empty():
    # replica-brokers are empty
    assignment = {
        "version": 1,
        "partitions": [{"partition": 0, "topic": 't1', "replicas": []}]
    }

    # Verify validation failed
    assert _validate_format(assignment) is False


def test_validate_assignment():
    assignment = {
        "version": 1,
        "partitions": [
            {"partition": 0, "topic": 't1', "replicas": [0, 1]},
            {"partition": 1, "topic": 't1', "replicas": [1, 2]},
        ]
    }

    # Verify valid assignment
    assert _validate_assignment(assignment) is True


def test_validate_assignment_duplicate_partitions():
    # Duplicate partition (t1, 0)
    assignment = {
        "version": 1,
        "partitions": [
            {"partition": 0, "topic": 't1', "replicas": [0, 1]},
            {"partition": 0, "topic": 't1', "replicas": [1, 2]},
        ]
    }

    # Verify validation failed
    assert _validate_assignment(assignment) is False


def test_validate_assignment_duplicate_replica_brokers():
    # Duplicate replica-brokers [0, 0, 1]
    assignment = {
        "version": 1,
        "partitions": [{"partition": 0, "topic": 't1', "replicas": [0, 0, 1]}]
    }

    # Verify validation failed
    assert _validate_assignment(assignment) is False


def test_validate_assignment_different_replication_factor():
    # Replication-factor (t1, 0): 2
    # Replication-factor (t1, 1): 3
    assignment = {
        "version": 1,
        "partitions": [
            {"partition": 0, "topic": 't1', "replicas": [0, 2, 1]},
            {"partition": 1, "topic": 't1', "replicas": [0, 1]}
        ]
    }

    # Verify validation failed
    assert _validate_assignment(assignment) is False


def test_validate_plan_base():
    assignment = {
        "version": 1,
        "partitions": [
            {"partition": 0, "topic": 't1', "replicas": [1, 2]},
            {"partition": 1, "topic": 't1', "replicas": [0, 1]}
        ]
    }
    base_assignment = {
        "version": 1,
        "partitions": [
            {"partition": 0, "topic": 't1', "replicas": [0, 2]},
            {"partition": 1, "topic": 't1', "replicas": [1, 2]},
            {"partition": 1, "topic": 't2', "replicas": [0]}
        ]
    }

    # Verify valid assignment compared to base
    assert _validate_plan_base(assignment, base_assignment) is True


def test_validate_plan_base_invalid_partitions():
    # partition: ('invalid', 0) not present in base assignment
    assignment = {
        "version": 1,
        "partitions": [
            {"partition": 0, "topic": 't1', "replicas": [1, 2]},
            {"partition": 0, "topic": 'invalid', "replicas": [0, 1]}
        ]
    }
    base_assignment = {
        "version": 1,
        "partitions": [
            {"partition": 0, "topic": 't1', "replicas": [0, 2]},
            {"partition": 0, "topic": 't2', "replicas": [0, 1]}
        ]
    }

    # Verify validation failed
    assert _validate_plan_base(assignment, base_assignment) is False


def test_validate_plan_base_invalid_partitions_2():
    # partition: ('t2', 1) not present in base assignment
    assignment = {
        "version": 1,
        "partitions": [
            {"partition": 0, "topic": 't1', "replicas": [1, 2]},
            {"partition": 1, "topic": 't2', "replicas": [0, 1]}
        ]
    }
    base_assignment = {
        "version": 1,
        "partitions": [
            {"partition": 0, "topic": 't1', "replicas": [0, 2]},
            {"partition": 0, "topic": 't2', "replicas": [0, 1]}
        ]
    }

    # Verify validation failed
    assert _validate_plan_base(assignment, base_assignment) is False


def test_validate_plan_base_replication_factor_changed():
    # replication-factor of (t1, 0) is 1 in assignment and 2 in base-assignment
    assignment = {
        "version": 1,
        "partitions": [
            {"partition": 0, "topic": 't1', "replicas": [1]},
            {"partition": 0, "topic": 't2', "replicas": [0, 1]}
        ]
    }
    base_assignment = {
        "version": 1,
        "partitions": [
            {"partition": 0, "topic": 't1', "replicas": [0, 2]},
            {"partition": 0, "topic": 't2', "replicas": [0, 1]}
        ]
    }

    # Verify validation failed
    assert _validate_plan_base(assignment, base_assignment) is False


def test_validate_plan_base_invalid_brokers():
    # Broker 4 in partition-replicas (t1, 0): [0, 4] is not present in
    # base assignment
    assignment = {
        "version": 1,
        "partitions": [
            {"partition": 0, "topic": 't1', "replicas": [1, 4]},
            {"partition": 0, "topic": 't2', "replicas": [0, 1]}
        ]
    }
    base_assignment = {
        "version": 1,
        "partitions": [
            {"partition": 0, "topic": 't1', "replicas": [0, 2]},
            {"partition": 0, "topic": 't2', "replicas": [0, 1]}
        ]
    }

    # Verify validation failed
    assert _validate_plan_base(assignment, base_assignment) is False


def test_validate_plan_1():
    # Only given assignment without base assignment
    assignment = {
        "version": 1,
        "partitions": [
            {"partition": 0, "topic": 't1', "replicas": [1, 4]},
            {"partition": 0, "topic": 't2', "replicas": [0, 1]}
        ]
    }

    # Verify valid plan
    assert validate_plan(assignment) is True


def test_validate_plan_2():
    # All partitions in new-plan
    assignment = {
        "version": 1,
        "partitions": [
            {"partition": 0, "topic": 't1', "replicas": [2, 1, 0]},
            {"partition": 1, "topic": 't1', "replicas": [0, 1, 2]},
            {"partition": 0, "topic": 't2', "replicas": [0, 3]}
        ]
    }
    base_assignment = {
        "version": 1,
        "partitions": [
            {"partition": 0, "topic": 't1', "replicas": [0, 2, 3]},
            {"partition": 1, "topic": 't1', "replicas": [0, 1, 2]},
            {"partition": 0, "topic": 't2', "replicas": [0, 1]}
        ]
    }

    # Verify valid plan
    assert validate_plan(assignment, base_assignment, is_partition_subset=False) is True


def test_validate_plan_incomplete_partition_subset():
    # All partitions in new-plan
    # Given complete-assignment partition-set incomplete
    complete_assignment = {
        "version": 1,
        "partitions": [
            {"partition": 0, "topic": 't1', "replicas": [2, 1, 0]},
            {"partition": 1, "topic": 't1', "replicas": [0, 1, 2]},
        ]
    }
    base_assignment = {
        "version": 1,
        "partitions": [
            {"partition": 0, "topic": 't1', "replicas": [0, 2, 3]},
            {"partition": 1, "topic": 't1', "replicas": [0, 1, 2]},
            {"partition": 0, "topic": 't2', "replicas": [0, 1]}
        ]
    }

    # Verify valid plan
    assert validate_plan(
        complete_assignment,
        base_assignment,
        is_partition_subset=False,
    ) is False


def test_validate_plan_incomplete_partition_subset_2():
    # All partitions in new-plan
    # Given complete-assignment partition-set superset
    complete_assignment = {
        "version": 1,
        "partitions": [
            {"partition": 0, "topic": 't1', "replicas": [2, 1, 0]},
            {"partition": 1, "topic": 't1', "replicas": [0, 1, 2]},
            {"partition": 0, "topic": 't2', "replicas": [0, 1]},
            {"partition": 0, "topic": 't3', "replicas": [0, 1]}
        ]
    }
    base_assignment = {
        "version": 1,
        "partitions": [
            {"partition": 0, "topic": 't1', "replicas": [0, 2, 3]},
            {"partition": 1, "topic": 't1', "replicas": [0, 1, 2]},
            {"partition": 0, "topic": 't2', "replicas": [0, 1]}
        ]
    }

    # Verify valid plan
    assert validate_plan(
        complete_assignment,
        base_assignment,
        is_partition_subset=False,
    ) is False


def test_validate_plan_3():
    assignment = {
        "version": 1,
        "partitions": [
            {"partition": 0, "topic": 't1', "replicas": [2, 1, 0]},
            {"partition": 0, "topic": 't2', "replicas": [0, 3]}
        ]
    }
    base_assignment = {
        "version": 1,
        "partitions": [
            {"partition": 0, "topic": 't1', "replicas": [0, 2, 3]},
            {"partition": 1, "topic": 't1', "replicas": [0, 1, 2]},
            {"partition": 0, "topic": 't2', "replicas": [0, 1]}
        ]
    }

    # Verify valid plan
    assert validate_plan(assignment, base_assignment) is True


def test_validate_plan_invalid_format():
    # Invalid format: partition-id string
    assignment = {
        "version": 1,
        "partitions": [
            {"partition": '0', "topic": 't1', "replicas": [2, 1, 0]},
            {"partition": 0, "topic": 't2', "replicas": [0, 3]}
        ]
    }
    base_assignment = {
        "version": 1,
        "partitions": [
            {"partition": 0, "topic": 't1', "replicas": [0, 2, 3]},
            {"partition": 1, "topic": 't1', "replicas": [0, 1, 2]},
            {"partition": 0, "topic": 't2', "replicas": [0, 1]}
        ]
    }

    # Verify validation failed
    assert validate_plan(assignment, base_assignment) is False


def test_validate_plan_duplicate_partition():
    # Invalid assignment: Duplicate partition
    assignment = {
        "version": 1,
        "partitions": [
            {"partition": 0, "topic": 't1', "replicas": [2, 1, 0]},
            {"partition": 0, "topic": 't1', "replicas": [0, 3]}
        ]
    }

    # Verify validation failed
    assert validate_plan(assignment) is False


def test_validate_plan_invalid_plan():
    # Invalid plan: Invalid replica-broker 9
    assignment = {
        "version": 1,
        "partitions": [
            {"partition": 0, "topic": 't1', "replicas": [2, 9, 0]},
            {"partition": 0, "topic": 't2', "replicas": [0, 3]}
        ]
    }
    base_assignment = {
        "version": 1,
        "partitions": [
            {"partition": 0, "topic": 't1', "replicas": [0, 2, 3]},
            {"partition": 1, "topic": 't1', "replicas": [0, 1, 2]},
            {"partition": 0, "topic": 't2', "replicas": [0, 1]}
        ]
    }
    # Verify validation failed
    assert validate_plan(assignment, base_assignment) is False


def irange(n):
    return [x for x in range(n)]
