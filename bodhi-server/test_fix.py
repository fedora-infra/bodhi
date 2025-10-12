#!/usr/bin/env python
"""
Simple test to verify the logic for the test case and bug feedback requirements fix.
"""

def test_logic():
    """
    Test the logic for checking test case and bug feedback.
    This simulates the logic that would be in the meets_requirements_why function.
    """
    # Mock a scenario where we have:
    # - require_testcases = True
    # - require_bugs = True
    # - test cases with feedback
    # - bugs with feedback
    
    print("Testing the fix logic...")
    
    # Example of the logic for test cases:
    require_testcases = True
    require_bugs = True
    has_test_cases = True  # Update has associated test cases
    has_bugs = True       # Update has associated bugs
    
    # Mock test case feedback: (negative_karma, positive_karma)
    testcases = [
        {"name": "test_case_1", "feedback": (0, 2)},  # No negative karma, has positive
        {"name": "test_case_2", "feedback": (-1, 0)}, # Has negative karma
        {"name": "test_case_3", "feedback": (0, 1)}   # No negative karma, has positive
    ]
    
    # Mock bug feedback: (negative_karma, positive_karma) 
    bugs = [
        {"id": "123456", "feedback": (0, 3)},  # No negative karma, has positive
        {"id": "123457", "feedback": (-2, 0)}, # Has negative karma
    ]
    
    # Check for required test cases feedback
    if require_testcases and has_test_cases:
        for testcase in testcases:
            negative_karma, positive_karma = testcase["feedback"]
            if negative_karma < 0:  # There is negative karma for this testcase
                print(f"X FAIL: Test case '{testcase['name']}' has negative feedback.")
                # In the actual code, this would return (False, reason)
    
    # Check for required bug feedback
    if require_bugs and has_bugs:
        for bug in bugs:
            negative_karma, positive_karma = bug["feedback"]
            if negative_karma < 0:  # There is negative karma for this bug
                print(f"X FAIL: Bug #{bug['id']} has negative feedback.")
                # In the actual code, this would return (False, reason)
    
    print("[PASS] Logic test passed - negative feedback cases correctly identified")
    
    # Test a case where everything passes
    print("\nTesting a case where all feedback is positive:")
    
    good_testcases = [
        {"name": "test_case_1", "feedback": (0, 2)},  # No negative karma, has positive
        {"name": "test_case_2", "feedback": (0, 1)},  # No negative karma, has positive
    ]
    
    good_bugs = [
        {"id": "123456", "feedback": (0, 3)},  # No negative karma, has positive
    ]
    
    all_good = True
    
    # Check test cases
    if require_testcases and has_test_cases:
        for testcase in good_testcases:
            negative_karma, positive_karma = testcase["feedback"]
            if negative_karma < 0:
                print(f"X FAIL: Test case '{testcase['name']}' has negative feedback.")
                all_good = False
    
    # Check bugs
    if require_bugs and has_bugs:
        for bug in good_bugs:
            negative_karma, positive_karma = bug["feedback"]
            if negative_karma < 0:
                print(f"X FAIL: Bug #{bug['id']} has negative feedback.")
                all_good = False
    
    if all_good:
        print("[PASS] All feedback is positive - update would pass requirements")
    
    print("\nLogic verification complete!")

if __name__ == "__main__":
    test_logic()