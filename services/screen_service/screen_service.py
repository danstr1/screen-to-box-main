from tinydb import TinyDB, Query
from typing import Optional, List, Dict


class ScreenService:
    """Service layer for screen management database operations"""
    
    def __init__(self, db_path: str = 'boxes.json'):
        """Initialize the service with database connection"""
        self.db = TinyDB(db_path)
        self.screens_table = self.db.table('screens')
        self.screen_query = Query()
    
    def _get_next_screen_id(self) -> int:
        """Generate the next screen ID by finding the maximum existing ID + 1"""
        all_screens = self.screens_table.all()
        if not all_screens:
            return 1
        max_id = max(screen.get('screen_id', 0) for screen in all_screens)
        return max_id + 1
    
    def create_screen(self, port_number: str, vlan_number: Optional[str] = None, screen_number: Optional[str] = None) -> Dict:
        """Create a new screen and return it"""
        screen_id = self._get_next_screen_id()
        new_screen = {
            'screen_id': screen_id,
            'screen_number': screen_number,
            'port_number': port_number,
            'vlan_number': vlan_number,
            'box_id': None  # 1-to-1 relationship with box
        }
        self.screens_table.insert(new_screen)
        return new_screen
    
    def delete_screen(self, screen_id: int) -> bool:
        """Delete a screen by ID. Returns True if deleted, False if not found"""
        result = self.screens_table.remove(self.screen_query.screen_id == screen_id)
        return len(result) > 0
    
    def get_screen_by_id(self, screen_id: int) -> Optional[Dict]:
        """Get a screen by its ID. Returns None if not found"""
        result = self.screens_table.search(self.screen_query['screen_id'] == screen_id)
        return result[0] if result else None
    
    def get_screen_by_box_id(self, box_id: int) -> Optional[Dict]:
        """Get a screen assigned to a specific box. Returns None if not found"""
        result = self.screens_table.search(self.screen_query['box_id'] == box_id)
        return result[0] if result else None
    
    def get_all_screens(self) -> List[Dict]:
        """Get all screens"""
        return self.screens_table.all()
    
    def get_free_screens(self) -> List[Dict]:
        """Get all free screens (screens with box_id = None)"""
        return self.screens_table.search(self.screen_query.box_id == None)
    
    def assign_box_to_screen(self, box_id: int, screen_id: int) -> Optional[Dict]:
        """Assign a box to a specific screen (1-to-1). Returns the updated screen or None if not found"""
        screen = self.get_screen_by_id(screen_id)
        if not screen:
            return None
        if screen['box_id'] == box_id and screen['screen_id'] == screen_id:
            return screen  # Already assigned to this box
        # Check if screen is already assigned to a box
        if screen['box_id'] is not None:
            return None  # Indicates screen is already assigned
        
        # Check if box is already assigned to another screen
        existing_screen = self.get_screen_by_box_id(box_id)
        if existing_screen:
            return None  # Box is already assigned to another screen
        
        # Assign box to screen
        self.screens_table.update({'box_id': box_id}, self.screen_query["screen_id"] == screen_id)
        screen['box_id'] = box_id
        return screen
    
    def unassign_box_from_screen(self, box_id: int) -> bool:
        """Unassign a box from its screen. Returns True if unassigned, False if box has no screen"""
        result = self.screens_table.search(self.screen_query.box_id == box_id)
        if not result:
            return False
        
        self.screens_table.update({'box_id': None}, self.screen_query.box_id == box_id)
        return True
    
    def unassign_screen(self, screen_id: int) -> Optional[bool]:
        """Unassign a screen by screen_id. Returns True if unassigned, False if already free, None if not found"""
        screen = self.get_screen_by_id(screen_id)
        if not screen:
            return None
        
        if screen['box_id'] is None:
            return False  # Already free
        
        self.screens_table.update({'box_id': None}, self.screen_query.screen_id == screen_id)
        return True
    
    def update_screen(self, screen_id: int, screen_number: Optional[str] = None, port_number: Optional[str] = None, vlan_number: Optional[str] = None) -> Optional[Dict]:
        """Update screen attributes. Returns the updated screen or None if not found"""
        screen = self.get_screen_by_id(screen_id)
        if not screen:
            return None
        
        update_data = {}
        if screen_number is not None:
            update_data['screen_number'] = screen_number
        if port_number is not None:
            update_data['port_number'] = port_number
        if vlan_number is not None:
            update_data['vlan_number'] = vlan_number
        
        if not update_data:
            return screen  # No updates to make, return existing screen
        
        self.screens_table.update(update_data, self.screen_query['screen_id'] == screen_id)
        
        # Return updated screen
        updated_screen = self.get_screen_by_id(screen_id)
        return updated_screen

