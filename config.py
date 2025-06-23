"""
Shared configuration for IDS automation tools
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Confluence configuration
CONFLUENCE_URL = os.getenv('CONFLUENCE_URL')
USERNAME = os.getenv('CONFLUENCE_USERNAME')
API_TOKEN = os.getenv('CONFLUENCE_API_TOKEN')
PAGE_ID = os.getenv('H2_PAGE_ID')
H2_PAGE_TABLE_HEADER = os.getenv('H2_PAGE_TABLE_HEADER')

# Jira configuration
JIRA_URL = os.getenv('CONFLUENCE_URL')
JIRA_PROJECT = os.getenv('JIRA_PROJECT')
ISSUE_TYPE = "Epic"

# Validation function
def validate_config():
    """Validate that all required configuration is present"""
    required_vars = [
        ('CONFLUENCE_URL', CONFLUENCE_URL),
        ('CONFLUENCE_USERNAME', USERNAME),
        ('CONFLUENCE_API_TOKEN', API_TOKEN),
        ('H2_PAGE_ID', PAGE_ID),
        ('JIRA_PROJECT', JIRA_PROJECT)
    ]
    
    missing_vars = [name for name, value in required_vars if not value]
    
    if missing_vars:
        return False, missing_vars
    
    return True, [] 