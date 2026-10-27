from aiogram.fsm.state import State, StatesGroup
 
 
class Registration(StatesGroup):
    waiting_for_team_name = State()
    waiting_for_captain_contact = State()
    waiting_for_mmr = State()
    waiting_for_players = State()
    waiting_for_substitutes = State()
    waiting_for_confirm = State()