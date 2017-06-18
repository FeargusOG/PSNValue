import json
import requests
import collections
import time
from django.db import transaction
from psycopg2 import IntegrityError
from django.utils import timezone
from datetime import datetime
from .models import Library, GameList, GamePrice, GameRatings, GameValue
from .generic_library import GenericLibrary

#PSN Library Name
PSN_MODEL_LIBRARY_NAME = 'PS4'
#PSN Default Rating Value
PSN_MODEL_RATING_DEFAULT_VALUE = 1
#PSN Default Rating Count
PSN_MODEL_RATING_DEFAULT_COUNT = 0
#PSN Default Free Value - anything less than one causes division by zero errors
PSN_MODEL_PRICE_FREE = 1
#PSN Library Total Results
PSN_JSON_ELEM_TOTAL_RESULTS = 'total_results'
#PSN Each Game JSON element
PSN_JSON_ELEM_EACH_GAME = 'links'
#PSN Sub-Base Game JSON element i.e. bundles etc.
PSN_JSON_ELEM_SUB_GAME = 'parent_name'
#PSN Game release date
PSN_JSON_ELEM_RELEASE_DATE = 'release_date'
#PSN Game ID JSON element
PSN_JSON_ELEM_GAME_ID = 'id'
#PSN Game Name JSON element
PSN_JSON_ELEM_GAME_NAME = 'name'
#PSN Game Full Detials URL JSON element
PSN_JSON_ELEM_GAME_URL = 'url'
#PSN Game Platform List JSON element
PSN_JSON_ELEM_GAME_PFORMS = 'playable_platform'
#PSN Game PS4 Platform Title
PSN_JSON_ELEM_GAME_PS4_PFORM = 'PS4™'
#PSN Game Image list JSON element
PSN_JSON_ELEM_GAME_IMAGES = 'images'
#PSN Game Image type JSON element
PSN_JSON_ELEM_GAME_IMGTYPE = 'type'
#PSN Game Image thumb type
PSN_JSON_ELEM_GAME_IMGTYPE_THUMB = 1
#PSN Game Age Rating JSON element - part of the full game details json!
PSN_JSON_ELEM_GAME_AGERATING = 'age_limit'
#PSN Default Age Rating
PSN_DEFAULT_AGE_RATING = 0
#PSN Main Game details block
PSN_JSON_ELEM_GAME_PRICE_BLOCK = 'default_sku'
#PSN Base Price JSON element - part of the full game details json!
PSN_JSON_ELEM_GAME_BASE_PRICE = 'price'
#PSN Base Discount JSON element - part of the full game details json!
PSN_JSON_ELEM_GAME_REWARDS = 'rewards'
#PSN Base Discount JSON element - part of the full game details json!
PSN_JSON_ELEM_GAME_BASE_DISCOUNT = 'discount'
#PSN PS Plus Discount JSON element - part of the full game details json!
PSN_JSON_ELEM_GAME_BONUS_DISCOUNT = 'bonus_discount'
#PSN Game Rating Parent Block - part of the full game details json!
PSN_JSON_ELEM_GAME_RATING_BLOCK = 'star_rating'
#PSN Game Rating Parent Block - part of the full game details json!
PSN_JSON_ELEM_GAME_RATING_VALUE = 'score'
#PSN Game Rating Parent Block - part of the full game details json!
PSN_JSON_ELEM_GAME_RATING_COUNT = 'total'

class PSNLibrary(GenericLibrary):
    def update_psn_lib(self, p_library_id):
        count = 0

        # Get the Library JSON
        psn_lib_json = self.get_psn_lib_json()

        # Set Library statistics for rating weighting
        list_of_game_ratings = super().get_list_of_all_game_ratings()
        self.m_stdev = super().calculate_standard_deviation(list_of_game_ratings)
        super().set_standard_deviation(p_library_id, self.m_stdev)
        self.m_mean = super().calculate_mean(list_of_game_ratings)
        super().set_mean(p_library_id, self.m_mean)
        
        for eachGame in psn_lib_json[PSN_JSON_ELEM_EACH_GAME]:
            if(self.game_is_valid(eachGame)):
                if(super().game_exists_in_db(p_library_id, eachGame[PSN_JSON_ELEM_GAME_ID])):
                    print("Game exists: ", eachGame[PSN_JSON_ELEM_GAME_NAME])
                    self.update_psn_game(eachGame)
                    count += 1
                else:
                    print("Game doesn't exist: ", eachGame[PSN_JSON_ELEM_GAME_NAME])
                    try:
                        self.add_psn_game(p_library_id, eachGame)
                    except Exception as e:
                        print("Exception: ", e)
                    
                    time.sleep(1)

                #count += 1
                #if count == 5:
                #    break

        # Update the Library 'Last Updated' field
        super().set_library_last_updated(p_library_id, timezone.now())

    @transaction.atomic #TODO placeholder func
    def update_psn_game(self, p_base_game_json):
        game_id = super().get_id_for_game_id(p_base_game_json[PSN_JSON_ELEM_GAME_ID])
        full_details_json = self.get_psn_game_json(super().get_game_details_url_from_db(p_base_game_json[PSN_JSON_ELEM_GAME_ID]))
        print("Updating game: ", p_base_game_json[PSN_JSON_ELEM_GAME_NAME])
        print("This game has id: ", super().get_id_for_game_id(p_base_game_json[PSN_JSON_ELEM_GAME_ID]))
        # Update the price
        self.update_psn_game_price(game_id, full_details_json)
        # Update the ratings (both new ratings in psn and updated weighting)
        self.update_psn_game_ratings(game_id, full_details_json[PSN_JSON_ELEM_GAME_RATING_BLOCK])
        # Update the GameValue entry
        self.update_psn_game_value(game_id)

    @transaction.atomic
    def add_psn_game(self, p_library_id, p_base_game_json):
        g_id = p_base_game_json[PSN_JSON_ELEM_GAME_ID]
        g_name = p_base_game_json[PSN_JSON_ELEM_GAME_NAME]
        g_url = p_base_game_json[PSN_JSON_ELEM_GAME_URL]
        g_thumb = self.get_psn_thumbnail(p_base_game_json[PSN_JSON_ELEM_GAME_IMAGES])
        g_age = PSN_DEFAULT_AGE_RATING
        print("Adding game: ", g_name, " - ", g_url)
        game_entry = super().add_game_list_entry_to_db(g_id, g_name, g_url, g_thumb, g_age, Library.objects.get(pk=p_library_id))
        self.add_psn_full_game_details(game_entry)

    def add_psn_full_game_details(self, p_game_entry):
        full_details_json = self.get_psn_game_json(p_game_entry.json_url)
        print("Game: ",full_details_json[PSN_JSON_ELEM_GAME_NAME],"- Age: ",full_details_json[PSN_JSON_ELEM_GAME_AGERATING])
        #Update the age rating
        g_age = full_details_json[PSN_JSON_ELEM_GAME_AGERATING]
        super().set_game_age_rating(p_game_entry, g_age)
        #Add a GamePrice entry
        self.add_psn_game_price(p_game_entry, full_details_json)
        #Add a GameRatings entry
        self.add_psn_game_ratings(p_game_entry, full_details_json[PSN_JSON_ELEM_GAME_RATING_BLOCK])
        #Add a GameValue entry
        self.add_psn_game_value(p_game_entry)

    def update_psn_game_price(self, p_game_id, p_game_full_details_json):
        g_price = p_game_full_details_json[PSN_JSON_ELEM_GAME_PRICE_BLOCK][PSN_JSON_ELEM_GAME_BASE_PRICE]
        g_discount_tuple = self.get_psn_game_discounts(p_game_full_details_json[PSN_JSON_ELEM_GAME_PRICE_BLOCK])
        super().update_game_price_entry(p_game_id, g_price, g_discount_tuple.base, g_discount_tuple.plus)

    def add_psn_game_price(self, p_game_entry, p_game_full_details_json):
        g_price = p_game_full_details_json[PSN_JSON_ELEM_GAME_PRICE_BLOCK][PSN_JSON_ELEM_GAME_BASE_PRICE]
        g_discount_tuple = self.get_psn_game_discounts(p_game_full_details_json[PSN_JSON_ELEM_GAME_PRICE_BLOCK])
        super().add_game_price_entry(p_game_entry, g_price, g_discount_tuple.base, g_discount_tuple.plus)

    def get_psn_game_discounts(self, p_game_price_block_json):
        psn_discounts = collections.namedtuple('psn_discounts', ['base', 'plus'])
        base_discount = 0
        plus_discount = 0
        if (PSN_JSON_ELEM_GAME_REWARDS in p_game_price_block_json) and (p_game_price_block_json[PSN_JSON_ELEM_GAME_REWARDS]):
            print(type(p_game_price_block_json[PSN_JSON_ELEM_GAME_REWARDS]))
            if PSN_JSON_ELEM_GAME_BASE_DISCOUNT in p_game_price_block_json[PSN_JSON_ELEM_GAME_REWARDS][0]:
                base_discount = p_game_price_block_json[PSN_JSON_ELEM_GAME_REWARDS][0][PSN_JSON_ELEM_GAME_BASE_DISCOUNT]
            if PSN_JSON_ELEM_GAME_BONUS_DISCOUNT in p_game_price_block_json[PSN_JSON_ELEM_GAME_REWARDS][0]:
                plus_discount = p_game_price_block_json[PSN_JSON_ELEM_GAME_REWARDS][0][PSN_JSON_ELEM_GAME_BONUS_DISCOUNT]

        return psn_discounts(base=base_discount,plus=plus_discount)

    def add_psn_game_ratings(self, p_game_entry, p_game_rating_block_json):
        g_rating_value = p_game_rating_block_json[PSN_JSON_ELEM_GAME_RATING_VALUE] if p_game_rating_block_json[PSN_JSON_ELEM_GAME_RATING_VALUE] else PSN_MODEL_RATING_DEFAULT_VALUE
        g_rating_count = p_game_rating_block_json[PSN_JSON_ELEM_GAME_RATING_COUNT] if p_game_rating_block_json[PSN_JSON_ELEM_GAME_RATING_COUNT] else PSN_MODEL_RATING_DEFAULT_COUNT
        super().add_game_rating_entry(p_game_entry, g_rating_value, g_rating_count, super().apply_weighted_game_rating(float(g_rating_value)))

    def update_psn_game_ratings(self, p_game_id, p_game_rating_block_json):
        g_rating_value = p_game_rating_block_json[PSN_JSON_ELEM_GAME_RATING_VALUE] if p_game_rating_block_json[PSN_JSON_ELEM_GAME_RATING_VALUE] else PSN_MODEL_RATING_DEFAULT_VALUE
        g_rating_count = p_game_rating_block_json[PSN_JSON_ELEM_GAME_RATING_COUNT] if p_game_rating_block_json[PSN_JSON_ELEM_GAME_RATING_COUNT] else PSN_MODEL_RATING_DEFAULT_COUNT
        super().update_game_rating_entry(p_game_id, g_rating_value, g_rating_count, super().apply_weighted_game_rating(float(g_rating_value)))

    def add_psn_game_value(self, p_game_entry):
        g_weighted_rating = super().get_game_weighted_rating(p_game_entry)
        g_price = super().get_game_price(p_game_entry)
        g_price = g_price if g_price > 0.0 else PSN_MODEL_PRICE_FREE
        print("Weighted Rating: ", g_weighted_rating)
        print("Price: ", g_price)
        #Calculate the value for this game
        g_val = super().calculate_game_value(g_weighted_rating, g_price)
        print("Value: ", g_val)
        #Add entry to DB for this game value
        super().add_game_value_entry(p_game_entry, g_val)

    def update_psn_game_value(self, p_game_id):
        g_weighted_rating = super().get_game_weighted_rating(p_game_id)
        g_price = super().get_game_price(p_game_id)
        g_price = g_price if g_price > 0.0 else PSN_MODEL_PRICE_FREE
        print("Updated Weighted Rating: ", g_weighted_rating)
        print("Updated Price: ", g_price)
        #Calculate the value for this game
        g_val = super().calculate_game_value(g_weighted_rating, g_price)
        print("Updated Value: ", g_val)
        #Add entry to DB for this game value
        super().update_game_value_entry(p_game_id, g_val)

    def get_psn_thumbnail(self, p_image_list):
        game_thumb = None
        for eachGameImg in p_image_list:
            if eachGameImg[PSN_JSON_ELEM_GAME_IMGTYPE] == PSN_JSON_ELEM_GAME_IMGTYPE_THUMB:
                game_thumb = eachGameImg[PSN_JSON_ELEM_GAME_URL]
                break
        return game_thumb

    def game_is_valid(self, p_game_json):
        game_valid = True
        # We're just looking for base games i.e. ignore bundles etc.
        # If a game is on sale, the bundle is (always?) on sale too.
        # Maybe we shouldn't be.... Do some tests on this.
        if PSN_JSON_ELEM_SUB_GAME in p_game_json:
            game_valid = False
        # Check to make sure the game is released - otherwise we can get games without prices etc.
        elif(self.game_is_released(p_game_json) == False):
            game_valid = False

        return game_valid

    def game_is_on_PS4(self, p_platform_list):
        return PSN_JSON_ELEM_GAME_PS4_PFORM in p_platform_list

    def game_is_released(self, p_lib_game_entry):
        g_is_released = False
        g_release_date = datetime.strptime(p_lib_game_entry[PSN_JSON_ELEM_RELEASE_DATE], '%Y-%m-%dT%H:%M:%SZ')
        if(g_release_date < datetime.now()):
            g_is_released = True
        return g_is_released

    def get_psn_lib_json(self):
        psn_lib_url = super().get_lib_url_from_db(PSN_MODEL_LIBRARY_NAME)
        lib_total_results = self.get_psn_lib_total_results(psn_lib_url)
        return self.make_psn_lib_json_api_request(psn_lib_url, lib_total_results)

    def get_psn_lib_total_results(self, p_psn_lib_url):
        response_json = requests.get(p_psn_lib_url+'0')
        psn_lib_json = response_json.json()
        return psn_lib_json[PSN_JSON_ELEM_TOTAL_RESULTS]

    def make_psn_lib_json_api_request(self, p_psn_lib_url, p_count_to_fetch):
        #File for testing only - live version will pull json from psn api
        #with open('staticfiles/psnvalue/TotalPS4GameLibrary.json') as data_file:    
        #    psn_lib_json = json.load(data_file)
        response_json = requests.get(p_psn_lib_url+str(p_count_to_fetch))
        psn_lib_json = response_json.json()
        return psn_lib_json

    def get_psn_game_json(self, p_game_url):
        #File for testing only - live version will pull json from psn api
        #with open('staticfiles/psnvalue/DragonAgeInquisition_FullGame.json') as data_file:
        #with open('staticfiles/psnvalue/DarkSoulsIII_FullGame.json') as data_file:
        #    psn_game_json = json.load(data_file)
        response_json = requests.get(p_game_url)
        psn_game_json = response_json.json()
        return psn_game_json