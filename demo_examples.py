"""
Built-in demo examples for the Autonomous Software Debugging Agent.
Each example provides a buggy code snippet/project spec, a test snippet/trigger, and the corresponding error log.
"""

DEMO_EXAMPLES = {
    "ZeroDivisionError (Empty List)": {
        "title": "Calculate Average (Empty List)",
        "code": '''def calculate_average(numbers):
    total = sum(numbers)
    count = len(numbers)
    return total / count

# Execution that triggers bug:
print(calculate_average([]))
''',
        "error_log": '''Traceback (most recent call last):
  File "main.py", line 6, in <module>
    print(calculate_average([]))
  File "main.py", line 4, in calculate_average
    return total / count
ZeroDivisionError: division by zero''',
        "test_code": '''def test_calculate_average():
    assert calculate_average([10, 20, 30]) == 20.0
    assert calculate_average([5]) == 5.0
    assert calculate_average([]) == 0.0
'''
    },

    "IndexError (Out of Bounds)": {
        "title": "Access Array Element (Out of Bounds)",
        "code": '''def get_third_element(items):
    return items[2]

# Execution that triggers bug:
print(get_third_element([10, 20]))
''',
        "error_log": '''Traceback (most recent call last):
  File "main.py", line 5, in <module>
    print(get_third_element([10, 20]))
  File "main.py", line 2, in get_third_element
    return items[2]
IndexError: list index out of range''',
        "test_code": '''def test_get_third_element():
    assert get_third_element([10, 20, 30]) == 30
    assert get_third_element([10, 20]) is None
'''
    },

    "TypeError (String/Int Concatenation)": {
        "title": "Calculate Discount (String Input)",
        "code": '''def apply_discount(price, discount_percent):
    discount_amount = price * (discount_percent / 100)
    return price - discount_amount

# Execution that triggers bug:
print(apply_discount(100, "20"))
''',
        "error_log": '''Traceback (most recent call last):
  File "main.py", line 6, in <module>
    print(apply_discount(100, "20"))
  File "main.py", line 2, in apply_discount
    discount_amount = price * (discount_percent / 100)
TypeError: unsupported operand type(s) for /: 'str' and 'int\'''',
        "test_code": '''def test_apply_discount():
    assert apply_discount(100, 20) == 80.0
    assert apply_discount(100, "20") == 80.0
'''
    },

    "KeyError (Missing Dictionary Key)": {
        "title": "Extract User Email (Missing Key)",
        "code": '''def get_user_email(user_profile):
    return user_profile["email"]

# Execution that triggers bug:
user = {"name": "Alice", "id": 101}
print(get_user_email(user))
''',
        "error_log": '''Traceback (most recent call last):
  File "main.py", line 6, in <module>
    print(get_user_email(user))
  File "main.py", line 2, in get_user_email
    return user_profile["email"]
KeyError: 'email\'''',
        "test_code": '''def test_get_user_email():
    assert get_user_email({"name": "Alice", "email": "alice@example.com"}) == "alice@example.com"
    assert get_user_email({"name": "Bob"}) is None or get_user_email({"name": "Bob"}) == ""
'''
    },

    "🔥 LRU Cache (Complex OOP Data Structure)": {
        "title": "LRU Cache (Capacity & Node Eviction Bug)",
        "code": '''class Node:
    def __init__(self, key=0, val=0):
        self.key = key
        self.val = val
        self.prev = None
        self.next = None

class LRUCache:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache = {}
        self.head = Node()
        self.tail = Node()
        self.head.next = self.tail
        self.tail.prev = self.head

    def _remove(self, node):
        prev = node.prev
        nxt = node.next
        prev.next = nxt
        nxt.prev = prev

    def _insert(self, node):
        nxt = self.head.next
        self.head.next = node
        node.prev = self.head
        node.next = nxt
        nxt.prev = node

    def get(self, key: int) -> int:
        if key in self.cache:
            node = self.cache[key]
            self._remove(node)
            self._insert(node)
            return node.val
        return -1

    def put(self, key: int, value: int) -> None:
        if key in self.cache:
            self._remove(self.cache[key])
        node = Node(key, value)
        self.cache[key] = node
        self._insert(node)
        # Bug: Does not evict the least recently used node when capacity exceeded!
''',
        "error_log": "",
        "test_code": '''def test_lru_cache():
    lru = LRUCache(2)
    lru.put(1, 1)
    lru.put(2, 2)
    assert lru.get(1) == 1
    lru.put(3, 3) # evicts key 2
    assert lru.get(2) == -1
    lru.put(4, 4) # evicts key 1
    assert lru.get(1) == -1
    assert lru.get(3) == 3
    assert lru.get(4) == 4
'''
    },

    "🔥 Kadane's Algorithm (Max Subarray with Negative Numbers)": {
        "title": "Max Subarray Sum (All Negative Edge Case)",
        "code": '''def max_subarray(nums):
    # Flawed initialization: fails when all numbers are negative!
    max_sum = 0
    current_sum = 0
    for num in nums:
        current_sum = max(0, current_sum + num)
        max_sum = max(max_sum, current_sum)
    return max_sum
''',
        "error_log": "",
        "test_code": '''def test_max_subarray():
    assert max_subarray([-2, 1, -3, 4, -1, 2, 1, -5, 4]) == 6
    assert max_subarray([-1, -2, -3]) == -1
    assert max_subarray([5]) == 5
'''
    },

    "🔥 Binary Search (Off-By-One & Mid Overflow Bug)": {
        "title": "Binary Search (Boundary & Empty Edge Cases)",
        "code": '''def binary_search(arr, target):
    # Bug: Off-by-one condition in while loop skips rightmost element
    low = 0
    high = len(arr) - 1
    while low < high:
        mid = (low + high) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            low = mid + 1
        else:
            high = mid - 1
    return -1
''',
        "error_log": "",
        "test_code": '''def test_binary_search():
    assert binary_search([1, 3, 5, 7, 9], 9) == 4
    assert binary_search([1, 3, 5, 7, 9], 1) == 0
    assert binary_search([1, 3, 5, 7, 9], 5) == 2
    assert binary_search([1, 3, 5, 7, 9], 6) == -1
    assert binary_search([], 3) == -1
'''
    }
}

# Project Presets for testing ZIP upload
DEMO_PROJECT_PRESETS = {
    "Python ZIP (ZeroDivisionError)": {
        "language": "python",
        "filename": "python_bug_project.zip",
        "files": {
            "main.py": '''def calculate_average(numbers):
    total = sum(numbers)
    count = len(numbers)
    return total / count
''',
            "test_main.py": '''import pytest
from main import calculate_average

def test_calculate_average_normal():
    assert calculate_average([10, 20, 30]) == 20.0

def test_calculate_average_empty():
    assert calculate_average([]) == 0.0
''',
            "requirements.txt": "pytest>=7.0.0\n"
        }
    },
    "Java Maven ZIP (NullPointerException)": {
        "language": "java",
        "filename": "java_bug_project.zip",
        "files": {
            "pom.xml": '''<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.example</groupId>
    <artifactId>java-bug-project</artifactId>
    <version>1.0-SNAPSHOT</version>
    <properties>
        <maven.compiler.source>11</maven.compiler.source>
        <maven.compiler.target>11</maven.compiler.target>
    </properties>
</project>''',
            "src/main/java/com/example/UserService.java": '''package com.example;

public class UserService {
    public static class User {
        private String name;
        public User(String name) { this.name = name; }
        public String getName() { return name; }
    }

    public String getUserGreeting(User user) {
        return "Hello " + user.getName();
    }
}''',
            "src/test/java/com/example/UserServiceTest.java": '''package com.example;

public class UserServiceTest {
    public static void main(String[] args) {
        UserService service = new UserService();
        System.out.println(service.getUserGreeting(null));
    }
}'''
        }
    }
}
