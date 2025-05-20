import sys
import os

# Add the project's backend root directory (the parent of 'core' and 'tests') to sys.path.
# This allows tests to import modules from 'core' as a top-level package.
#
# Explanation of path construction:
# __file__ refers to the absolute path of this conftest.py file:
#   e.g., /home/cator/projects/SmartInfo/backend/tests/conftest.py
# os.path.dirname(__file__) gives the directory of this file:
#   e.g., /home/cator/projects/SmartInfo/backend/tests
# os.path.join(os.path.dirname(__file__), '..') goes one level up:
#   e.g., /home/cator/projects/SmartInfo/backend/
# os.path.abspath() ensures it's an absolute path.
#
# This effectively makes the 'backend' directory a place where Python will look for modules.
project_backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, project_backend_root)

# You can add fixtures or other shared test configurations here if needed in the future.
