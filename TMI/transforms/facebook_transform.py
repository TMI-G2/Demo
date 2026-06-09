"""
transforms/facebook_transform.py
----------------------------------
Maltego Local Transform: Facebook Risk Assessment

STATUS: STUB — not yet implemented.

To activate:
  1. Add "facebook_profile" to config.APIFY_ACTORS
  2. Implement fetch_facebook_profile() in utils/apify_scraper.py
  3. Uncomment the @registry.register_transform decorator below
  4. Implement create_entities() following the Instagram pattern

Important note:
  Facebook is the most locked-down platform. Since Cambridge Analytica,
  Meta has blocked almost all third-party data access. Realistically
  expect to retrieve: name, bio, profile picture, and public posts only.
  Friends list, groups, and private content are inaccessible via any scraper.
"""

import logging
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform
from maltego_trx.transform import DiscoverableTransform

log = logging.getLogger(__name__)

# Uncomment when ready:
# from maltego_trx import registry
# @registry.register_transform(
#     display_name="Facebook: Assess Risk Profile",
#     input_entity="maltego.Person",
#     description="Scrapes a public Facebook profile and scores it for risk exposure.",
#     output_entities=["maltego.Person"],
#     transform_set="Social Media Risk Assessment",
# )
class FacebookRiskTransform(DiscoverableTransform):
    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
        response.addUIMessage(
            "Facebook transform is not yet implemented. "
            "See transforms/facebook_transform.py for setup instructions.",
            messageType="PartialError",
        )
