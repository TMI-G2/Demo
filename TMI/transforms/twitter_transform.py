"""
transforms/twitter_transform.py
---------------------------------
Maltego Local Transform: Twitter/X Risk Assessment

STATUS: STUB — not yet implemented.

To activate:
  1. Add "twitter_profile" to config.APIFY_ACTORS
     Recommended actor: apify/twitter-scraper
  2. Implement fetch_twitter_profile() in utils/apify_scraper.py
  3. Uncomment the @registry.register_transform decorator below
  4. Implement create_entities() following the Instagram pattern

Note on Twitter/X API restrictions:
  Twitter/X heavily restricted its API in 2023. Maltego's built-in
  connector is largely broken as a result. Apify maintains working
  scrapers that bypass this — use those instead of Maltego's connector.

Key Twitter-specific risk signals:
  - Real name in display name vs. anonymous handle
  - Location field (even approximate)
  - Bio content (age, school, relationship status)
  - Public reply threads (can reveal personal info)
  - Quote tweet patterns with strangers
"""

import logging
from maltego_trx.maltego import MaltegoMsg, MaltegoTransform
from maltego_trx.transform import DiscoverableTransform

log = logging.getLogger(__name__)

# Uncomment when ready:
# from maltego_trx import registry
# @registry.register_transform(
#     display_name="Twitter/X: Assess Risk Profile",
#     input_entity="maltego.Person",
#     description="Scrapes a Twitter/X profile and scores it for risk exposure.",
#     output_entities=["maltego.Person"],
#     transform_set="Social Media Risk Assessment",
# )
class TwitterRiskTransform(DiscoverableTransform):
    @classmethod
    def create_entities(cls, request: MaltegoMsg, response: MaltegoTransform):
        response.addUIMessage(
            "Twitter/X transform is not yet implemented. "
            "See transforms/twitter_transform.py for setup instructions.",
            messageType="PartialError",
        )
