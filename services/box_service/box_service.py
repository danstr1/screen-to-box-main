from tinydb import TinyDB, Query
from typing import Optional, List, Dict


class BoxService:
    """Service layer for box management database operations"""
    
    def __init__(self, db_path: str = 'boxes.json'):
        """Initialize the service with database connection"""
        self.db = TinyDB(db_path)
        self.boxes_table = self.db.table('boxes')
        self.box_query = Query()
    
    def _get_next_box_id(self) -> int:
        """Generate the next box ID by finding the maximum existing ID + 1"""
        all_boxes = self.boxes_table.all()
        if not all_boxes:
            return 1
        max_id = max(box.get('box_id', 0) for box in all_boxes)
        return max_id + 1
    
    def create_box(self, port_number: str, box_number: str, vlan_number: Optional[str] = None) -> Dict:
        """Create a new box and return it"""
        box_id = self._get_next_box_id()
        new_box = {
            'box_id': box_id,
            'box_number': box_number,
            'port_number': port_number,
            'vlan_number': vlan_number,
            'user_id': None
        }
        self.boxes_table.insert(new_box)
        return new_box
    
    def delete_box(self, box_id: int) -> bool:
        """Delete a box by ID. Returns True if deleted, False if not found"""
        result = self.boxes_table.remove(self.box_query.box_id == box_id)
        return len(result) > 0
    
    def get_box_by_id(self, box_id: int) -> Optional[Dict]:
        """Get a box by its ID. Returns None if not found"""
        result = self.boxes_table.search(self.box_query['box_id'] == box_id)
        return result[0] if result else None
    
    def get_box_by_user_id(self, user_id: str) -> Optional[Dict]:
        """Get a box assigned to a specific user. Returns None if not found"""
        result = self.boxes_table.search(self.box_query['user_id'] == user_id)
        return result[0] if result else None
    
    def get_all_boxes(self) -> List[Dict]:
        """Get all boxes"""
        return self.boxes_table.all()
    
    def get_free_boxes(self) -> List[Dict]:
        """Get all free boxes (boxes with user_id = None)"""
        return self.boxes_table.search(self.box_query.user_id == None)
    
    def assign_user_to_box(self, user_id: str, box_id: int) -> Optional[Dict]:
        """Assign a user to a specific box. Returns the updated box or None if not found"""
        box = self.get_box_by_id(box_id)
        if not box:
            return None
        
        # Check if box is already assigned
        if box['user_id'] is not None:
            return None  # Indicates box is already assigned
        
        # Assign user to box
        self.boxes_table.update({'user_id': str(user_id)}, self.box_query["box_id"] == box_id)
        box['user_id'] = user_id
        return box
    
    def assign_user_to_any_free_box(self, user_id: str) -> Optional[Dict]:
        """Assign a user to any free box. Returns the assigned box or None if no free boxes"""
        free_boxes = self.get_free_boxes()
        if not free_boxes:
            return None
        
        # Assign to the first free box
        box = free_boxes[0]
        self.boxes_table.update({'user_id': user_id}, self.box_query.box_id == box['box_id'])
        box['user_id'] = user_id
        return box
    
    def unassign_user_from_box(self, user_id: str) -> bool:
        """Unassign a user from their box. Returns True if unassigned, False if user has no box"""
        result = self.boxes_table.search(self.box_query.user_id == user_id)
        if not result:
            return False
        
        self.boxes_table.update({'user_id': None}, self.box_query.user_id == user_id)
        return True
    
    def unassign_box(self, box_id: int) -> Optional[bool]:
        """Unassign a box by box_id. Returns True if unassigned, False if already free, None if not found"""
        box = self.get_box_by_id(box_id)
        if not box:
            return None
        
        if box['user_id'] is None:
            return False  # Already free
        
        self.boxes_table.update({'user_id': None}, self.box_query.box_id == box_id)
        return True
    
    def unassign_user_if_exists(self, user_id: str) -> None:
        """Unassign a user from their box if they have one. Does nothing if user has no box"""
        self.boxes_table.update({'user_id': None}, self.box_query.user_id == user_id)
    
    def update_box(self, box_id: int, box_number: Optional[str] = None, port_number: Optional[str] = None, vlan_number: Optional[str] = None) -> Optional[Dict]:
        """Update box attributes. Returns the updated box or None if not found"""
        box = self.get_box_by_id(box_id)
        if not box:
            return None
        
        update_data = {}
        if box_number is not None:
            update_data['box_number'] = box_number
        if port_number is not None:
            update_data['port_number'] = port_number
        if vlan_number is not None:
            update_data['vlan_number'] = vlan_number
        
        if not update_data:
            return box  # No updates to make, return existing box
        
        self.boxes_table.update(update_data, self.box_query['box_id'] == box_id)
        
        # Return updated box
        updated_box = self.get_box_by_id(box_id)
        return updated_box

