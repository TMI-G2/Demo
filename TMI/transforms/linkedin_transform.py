"""
transforms/linkedin_transform.py
----------------------------------
Maltego Local Transform: LinkedIn Risk Assessment

STATUS: STUB — not yet implemented.

To activate:
  1. Add "linkedin_profile" to config.APIFY_ACTORS
  2. Implement fetch_linkedin_profile() in utils/apify_scraper.py
  3. Uncomment the @registry.register_transform decorator below
  4. Implement create_entities() following the Instagram pattern

Key LinkedIn-specific risk signals to add to the rubric:
  - Full name + employer combination (high PII)
  - School name + graduation year (can reveal age)
  - Phone/email in contact info section
  - Location (city/country)
  - Open to work status (signals vulnerability to social engineering)
"""

import logging
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform
from maltego_trx.transform import DiscoverableTransform

log = logging.getLogger(__name__)

# Uncomment this decorator when you're ready to activate the transform:
# from maltego_trx import registry
# @registry.register_transform(
#     display_name="LinkedIn: Assess Risk Profile",
#     input_entity="maltego.Person",
#     description="Scrapes a LinkedIn profile and scores it for PII exposure risk.",
#     output_entities=["maltego.Person"],
#     transform_set="Social Media Risk Assessment",
# )
class LinkedInRiskTransform(DiscoverableTransform):
    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
        response.addUIMessage(
            "LinkedIn transform is not yet implemented. "
            "See transforms/linkedin_transform.py for setup instructions.",
            messageType="PartialError",
        )
