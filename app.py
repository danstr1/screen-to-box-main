from flask import Flask, request, jsonify
import os
from services.box_service.box_service import BoxService
from services.screen_service.screen_service import ScreenService
from services.config_service.config_service import ConfigService
from services.cisco_worker.cisco_worker import CiscoWorker

app = Flask(__name__)

# Initialize services
box_service = BoxService()
screen_service = ScreenService()
config_service = ConfigService()

# Initialize Cisco worker
# Get serial port from database, fallback to environment variable or default
serial_port = config_service.get_serial_port(os.getenv('CISCO_SERIAL_PORT', 'COM4'))
cisco_worker = CiscoWorker(serial_port=serial_port)

# Error messages
ERROR_BOX_NOT_FOUND = 'Box not found'
ERROR_USER_NOT_FOUND = 'User has no assigned box'
ERROR_BOX_ALREADY_FREE = 'Box is already free'
ERROR_BOX_ALREADY_ASSIGNED = 'Box is already assigned to another user'
ERROR_NO_FREE_BOXES = 'No free boxes available'
ERROR_REQUEST_BODY_REQUIRED = 'Request body is required'
ERROR_SCREEN_NOT_FOUND = 'Screen not found'
ERROR_SCREEN_ALREADY_ASSIGNED = 'Screen is already assigned to another box'
ERROR_BOX_ALREADY_HAS_SCREEN = 'Box is already assigned to another screen'
ERROR_SCREEN_ALREADY_FREE = 'Screen is already free'


@app.route('/boxes', methods=['POST'])
def add_box():
    """Add a new box"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': ERROR_REQUEST_BODY_REQUIRED}), 400
    
    if 'port_number' not in data:
        return jsonify({'error': 'port_number is required'}), 400
    
    if 'box_number' not in data:
        return jsonify({'error': 'box_number is required'}), 400
    
    if 'vlan_number' not in data or not data['vlan_number']:
        return jsonify({'error': 'vlan_number is required'}), 400
    
    port_number = data['port_number']
    box_number = data['box_number']
    vlan_number = data['vlan_number']
    
    # Create new box
    new_box = box_service.create_box(port_number, box_number, vlan_number)
    
    return jsonify(new_box), 201


@app.route('/boxes/<int:box_id>', methods=['DELETE'])
def delete_box(box_id):
    """Delete a box"""
    deleted = box_service.delete_box(box_id)
    
    if not deleted:
        return jsonify({'error': ERROR_BOX_NOT_FOUND}), 404
    
    return jsonify({'message': 'Box deleted successfully'}), 200


@app.route('/boxes/assign', methods=['POST'])
def assign_box():
    """Assign a user to a box"""
    data = request.get_json()
    
    if not data or 'user_id' not in data:
        return jsonify({'error': 'user_id is required'}), 400
    
    user_id = data['user_id']
    box_id = data.get('box_id')
    
    # Check if user already has a box assigned and unassign it
    box_service.unassign_user_if_exists(user_id)
    
    # If box_id is provided, assign to that specific box
    if box_id:
        box = box_service.assign_user_to_box(str(user_id), box_id)
        if not box:
            # Check if box exists
            if not box_service.get_box_by_id(box_id):
                return jsonify({'error': ERROR_BOX_NOT_FOUND}), 404
            else:
                return jsonify({'error': ERROR_BOX_ALREADY_ASSIGNED}), 400
        
        return jsonify({
            'box_id': box['box_id'],
            'box_number': box.get('box_number', ''),
            'user_id': user_id,
            'port_number': box['port_number']
        }), 200
    else:
        # Find and assign to any free box
        box = box_service.assign_user_to_any_free_box(user_id)
        if not box:
            return jsonify({'error': ERROR_NO_FREE_BOXES}), 404
        
        return jsonify({
            'box_id': box['box_id'],
            'box_number': box.get('box_number', ''),
            'user_id': user_id,
            'port_number': box['port_number']
        }), 200


@app.route('/boxes/assign_user_to_free_box', methods=['POST'])
def assign_user_to_free_box():
    """Assign a user to any free box"""
    data = request.get_json()
    
    if not data or 'user_id' not in data:
        return jsonify({'error': 'user_id is required'}), 400
    
    user_id = data['user_id']
    
    # Check if user already has a box assigned and unassign it
    box_service.unassign_user_if_exists(user_id)
    
    # Find and assign to any free box
    box = box_service.assign_user_to_any_free_box(user_id)
    if not box:
        return jsonify({'error': ERROR_NO_FREE_BOXES}), 404
    
    return jsonify({
        'box_id': box['box_id'],
        'box_number': box.get('box_number', ''),
        'user_id': user_id,
        'port_number': box['port_number']
    }), 200


@app.route('/boxes/unassign', methods=['POST'])
def unassign_box():
    """Unassign a user from a box"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': ERROR_REQUEST_BODY_REQUIRED}), 400
    
    user_id = data.get('user_id')
    box_id = data.get('box_id')
    
    if user_id is None and box_id is None:
        return jsonify({'error': 'Either user_id or box_id is required'}), 400
    
    if user_id is not None:
        # Unassign by user_id
        unassigned = box_service.unassign_user_from_box(user_id)
        if not unassigned:
            return jsonify({'error': ERROR_USER_NOT_FOUND}), 404
        
        return jsonify({'message': 'User unassigned from box successfully'}), 200
    
    if box_id is not None:
        # Unassign by box_id
        result = box_service.unassign_box(box_id)
        if result is None:
            return jsonify({'error': ERROR_BOX_NOT_FOUND}), 404
        if result is False:
            return jsonify({'error': ERROR_BOX_ALREADY_FREE}), 400
        
        return jsonify({'message': 'Box unassigned successfully'}), 200


@app.route('/boxes/free', methods=['GET'])
def get_free_boxes():
    """Get all free boxes"""
    free_boxes = box_service.get_free_boxes()
    return jsonify(free_boxes), 200


@app.route('/boxes', methods=['GET'])
def get_all_boxes():
    """Get all boxes"""
    all_boxes = box_service.get_all_boxes()
    return jsonify(all_boxes), 200


@app.route('/boxes/user/<user_id>', methods=['GET'])
def get_user_box(user_id):
    """Get box assigned to a specific user"""
    
    box = box_service.get_box_by_user_id(user_id)
    if not box:
        return jsonify({'has_box': False}), 200
    
    return jsonify({
        'has_box': True,
        'box_id': box['box_id'],
        'box_number': box.get('box_number', ''),
        'user_id': user_id,
        'port_number': box['port_number']
    }), 200


@app.route('/boxes/<int:box_id>', methods=['PUT', 'PATCH'])
def update_box(box_id):
    """Update box attributes"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': ERROR_REQUEST_BODY_REQUIRED}), 400
    
    # Extract updatable fields
    box_number = data.get('box_number')
    port_number = data.get('port_number')
    vlan_number = data.get('vlan_number')
    
    # Check if at least one field is provided
    if box_number is None and port_number is None and vlan_number is None:
        return jsonify({'error': 'At least one field (box_number, port_number, or vlan_number) must be provided'}), 400
    
    # Update the box
    updated_box = box_service.update_box(box_id, box_number=box_number, port_number=port_number, vlan_number=vlan_number)
    
    if not updated_box:
        return jsonify({'error': ERROR_BOX_NOT_FOUND}), 404
    
    return jsonify(updated_box), 200


# Screen endpoints

@app.route('/screens', methods=['POST'])
def add_screen():
    """Add a new screen"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': ERROR_REQUEST_BODY_REQUIRED}), 400
    
    if 'port_number' not in data:
        return jsonify({'error': 'port_number is required'}), 400
    
    port_number = data['port_number']
    vlan_number = data.get('vlan_number')
    screen_number = data.get('screen_number')
    
    # Create new screen
    new_screen = screen_service.create_screen(port_number, vlan_number, screen_number)
    
    return jsonify(new_screen), 201


@app.route('/screens/<int:screen_id>', methods=['DELETE'])
def delete_screen(screen_id):
    """Delete a screen"""
    deleted = screen_service.delete_screen(screen_id)
    
    if not deleted:
        return jsonify({'error': ERROR_SCREEN_NOT_FOUND}), 404
    
    return jsonify({'message': 'Screen deleted successfully'}), 200


@app.route('/screens', methods=['GET'])
def get_all_screens():
    """Get all screens"""
    all_screens = screen_service.get_all_screens()
    return jsonify(all_screens), 200


@app.route('/screens/free', methods=['GET'])
def get_free_screens():
    """Get all free screens"""
    free_screens = screen_service.get_free_screens()
    return jsonify(free_screens), 200


@app.route('/screens/<int:screen_id>', methods=['GET'])
def get_screen(screen_id):
    """Get a specific screen by ID"""
    screen = screen_service.get_screen_by_id(screen_id)
    
    if not screen:
        return jsonify({'error': ERROR_SCREEN_NOT_FOUND}), 404
    
    return jsonify(screen), 200


@app.route('/screens/assign', methods=['POST'])
def assign_box_to_screen():
    """Assign a box to a screen (1-to-1 relation)"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': ERROR_REQUEST_BODY_REQUIRED}), 400
    
    box_id = data.get('box_id')
    screen_id = data.get('screen_id')
    
    if box_id is None or screen_id is None:
        return jsonify({'error': 'Both box_id and screen_id are required'}), 400
    
    # Check if box exists
    box = box_service.get_box_by_id(box_id)
    if not box:
        return jsonify({'error': ERROR_BOX_NOT_FOUND}), 404
    
    # Assign box to screen
    screen = screen_service.assign_box_to_screen(box_id, screen_id)
    if not screen:
        # Check if screen exists
        if not screen_service.get_screen_by_id(screen_id):
            return jsonify({'error': ERROR_SCREEN_NOT_FOUND}), 404
        # Check if screen is already assigned
        existing_screen = screen_service.get_screen_by_id(screen_id)
        if existing_screen and existing_screen.get('box_id') is not None:
            return jsonify({'error': ERROR_SCREEN_ALREADY_ASSIGNED}), 400
        # Check if box is already assigned to another screen
        existing_screen_for_box = screen_service.get_screen_by_box_id(box_id)
        if existing_screen_for_box:
            return jsonify({'error': ERROR_BOX_ALREADY_HAS_SCREEN}), 400
    
    # Physically assign screen port to box's VLAN on the switch
    if screen and box:
        screen_port = screen.get('port_number')
        box_vlan = box.get('vlan_number')
        
        if screen_port and box_vlan:
            try:
                if cisco_worker.connection and cisco_worker.connection.is_open:
                    success = cisco_worker.assign_port_to_vlan(screen_port, box_vlan)
                    if not success:
                        print(f"Warning: Failed to assign screen port {screen_port} to box VLAN {box_vlan} on switch")
            except Exception as e:
                print(f"Error assigning screen port to box VLAN on switch: {e}")
    
    return jsonify(screen), 200


@app.route('/screens/assign_user', methods=['POST'])
def assign_user_to_screen():
    """Assign a user's box to a screen. If screen is already assigned, reassign it."""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': ERROR_REQUEST_BODY_REQUIRED}), 400
    
    screen_id = data.get('screen_id')
    user_id = data.get('user_id')
    
    if screen_id is None or user_id is None:
        return jsonify({'error': 'Both screen_id and user_id are required'}), 400
    
    print(f"[INFO] Assigning user {user_id} to screen {screen_id}")
    
    # Check if screen exists
    screen = screen_service.get_screen_by_id(screen_id)
    if not screen:
        print(f"[ERROR] Screen {screen_id} not found")
        return jsonify({'error': ERROR_SCREEN_NOT_FOUND}), 404
    
    # Get the box assigned to the user
    box = box_service.get_box_by_user_id(user_id)
    if not box:
        print(f"[ERROR] User {user_id} has no assigned box")
        return jsonify({'error': ERROR_USER_NOT_FOUND}), 400
    
    box_id = box['box_id']
    print(f"[INFO] User {user_id} has box {box_id} (Box Number: {box.get('box_number')})")
    
    # If screen is already assigned to a different box, unassign it first
    if screen.get('box_id') is not None and screen.get('box_id') != box_id:
        old_box_id = screen.get('box_id')
        old_box = box_service.get_box_by_id(old_box_id)
        print(f"[INFO] Screen {screen_id} is assigned to different box {old_box_id}, unassigning...")
        
        # Unassign the screen from the old box
        screen_service.unassign_screen(screen_id)
        
        # Reset old box port to default VLAN on switch
        if old_box:
            old_box_port = old_box.get('port_number')
            if old_box_port:
                try:
                    if cisco_worker.connection and cisco_worker.connection.is_open:
                        default_vlan = old_box.get('vlan_number') or cisco_worker.default_box_vlan
                        print(f"[INFO] Resetting old box port {old_box_port} to VLAN {default_vlan}")
                        cisco_worker.assign_port_to_vlan(old_box_port, default_vlan)
                except Exception as e:
                    print(f"[ERROR] Error resetting old box port VLAN on switch: {e}")
    
    # If the new box is already assigned to another screen, unassign it first
    existing_screen_for_box = screen_service.get_screen_by_box_id(box_id)
    if existing_screen_for_box and existing_screen_for_box.get('screen_id') != screen_id:
        old_screen_id = existing_screen_for_box.get('screen_id')
        print(f"[INFO] Box {box_id} is assigned to different screen {old_screen_id}, unassigning...")
        
        # Unassign the box from the old screen
        screen_service.unassign_box_from_screen(box_id)
        
        # Reset old screen port to default VLAN 101 on switch (mark as disconnected)
        old_screen_port = existing_screen_for_box.get('port_number')
        if old_screen_port:
            try:
                if cisco_worker.connection and cisco_worker.connection.is_open:
                    default_screen_vlan = cisco_worker.default_screen_vlan
                    print(f"[INFO] Resetting old screen port {old_screen_port} to VLAN {default_screen_vlan} (disconnected)")
                    cisco_worker.assign_port_to_vlan(old_screen_port, default_screen_vlan)
            except Exception as e:
                print(f"[ERROR] Error resetting old screen port VLAN on switch: {e}")
        
        # Reset box port to default VLAN on switch
        box_port = box.get('port_number')
        if box_port:
            try:
                if cisco_worker.connection and cisco_worker.connection.is_open:
                    default_vlan = box.get('vlan_number') or cisco_worker.default_box_vlan
                    print(f"[INFO] Resetting box port {box_port} to VLAN {default_vlan}")
                    cisco_worker.assign_port_to_vlan(box_port, default_vlan)
            except Exception as e:
                print(f"[ERROR] Error resetting box port VLAN on switch: {e}")
    
    # Now assign box to screen (this will work since we've cleared any conflicts)
    print(f"[INFO] Assigning box {box_id} to screen {screen_id} in database")
    screen = screen_service.assign_box_to_screen(box_id, screen_id)
    if not screen:
        # This should not happen after clearing conflicts, but handle it just in case
        print(f"[ERROR] Failed to assign box {box_id} to screen {screen_id}")
        return jsonify({'error': 'Failed to assign box to screen'}), 500
    
    # Physically assign screen port to box's VLAN on the switch
    screen_port = screen.get('port_number')
    box_vlan = box.get('vlan_number')
    
    print(f"[INFO] Configuring switch: screen port {screen_port} to box VLAN {box_vlan}")
    if screen_port and box_vlan:
        try:
            if cisco_worker.connection and cisco_worker.connection.is_open:
                success = cisco_worker.assign_port_to_vlan(screen_port, box_vlan)
                if not success:
                    print(f"[WARNING] Failed to assign screen port {screen_port} to box VLAN {box_vlan} on switch")
                else:
                    print(f"[SUCCESS] Screen port {screen_port} configured to VLAN {box_vlan}")
        except Exception as e:
            print(f"[ERROR] Error assigning screen port to box VLAN on switch: {e}")
    
    print(f"[SUCCESS] User {user_id} assigned to screen {screen_id}")
    return jsonify(screen), 200


@app.route('/screens/unassign_all', methods=['POST'])
def unassign_all():
    """Unassign all boxes from all screens and remove all user assignments from boxes"""
    try:
        print("[INFO] Starting unassign_all operation...")
        
        # Get all screens that have assignments
        screens = screen_service.get_all_screens()
        assigned_screens = [s for s in screens if s.get('box_id') is not None]
        
        if not assigned_screens:
            print("[INFO] No screen assignments found")
            # Still check for user assignments in boxes
            boxes = box_service.get_all_boxes()
            assigned_boxes = [b for b in boxes if b.get('user_id') is not None]
            if not assigned_boxes:
                print("[INFO] No user assignments found")
                return jsonify({'message': 'No assignments to remove'}), 200
        
        print(f"[INFO] Found {len(assigned_screens)} assigned screens")
        
        # Collect all box IDs from assigned screens for user unassignment
        box_ids_to_unassign = set()
        for screen in assigned_screens:
            box_id = screen.get('box_id')
            if box_id:
                box_ids_to_unassign.add(box_id)
        
        success_count = 0
        failed_screens = []
        
        for idx, screen in enumerate(assigned_screens, 1):
            screen_id = screen.get('screen_id')
            screen_port = screen.get('port_number')
            box_id = screen.get('box_id')
            print(f"[INFO] Processing screen {idx}/{len(assigned_screens)}: ID={screen_id}, Port={screen_port}, Box={box_id}")
            
            # Unassign in database
            result = screen_service.unassign_screen(screen_id)
            if result:
                # Reset screen port to default VLAN 101 on switch
                if screen_port:
                    try:
                        if cisco_worker.connection and cisco_worker.connection.is_open:
                            default_screen_vlan = cisco_worker.default_screen_vlan
                            success = cisco_worker.assign_port_to_vlan(screen_port, default_screen_vlan)
                            if success:
                                success_count += 1
                                print(f"[SUCCESS] Screen {screen_id} port {screen_port} reset to VLAN {default_screen_vlan}")
                            else:
                                failed_screens.append(screen_port)
                                print(f"[ERROR] Failed to reset screen {screen_id} port {screen_port}")
                        else:
                            # Database updated but switch not connected
                            success_count += 1
                            print(f"[WARNING] Screen {screen_id} unassigned in DB but switch not connected")
                    except Exception as e:
                        failed_screens.append(screen_port)
                        print(f"[ERROR] Exception resetting screen {screen_id} port {screen_port}: {e}")
                else:
                    success_count += 1
            else:
                failed_screens.append(str(screen_id))
                print(f"[ERROR] Failed to unassign screen {screen_id}")
        
        # Now unassign users from all boxes that were assigned to screens
        users_unassigned = 0
        for box_id in box_ids_to_unassign:
            box = box_service.get_box_by_id(box_id)
            if box and box.get('user_id'):
                user_id = box.get('user_id')
                print(f"[INFO] Unassigning user {user_id} from box {box_id}")
                if box_service.unassign_user_from_box(user_id):
                    users_unassigned += 1
                    print(f"[SUCCESS] User {user_id} unassigned from box {box_id}")
                else:
                    print(f"[ERROR] Failed to unassign user {user_id} from box {box_id}")
        
        # Also unassign users from any other boxes that might have users but no screen assignment
        all_boxes = box_service.get_all_boxes()
        for box in all_boxes:
            if box.get('user_id') and box.get('box_id') not in box_ids_to_unassign:
                user_id = box.get('user_id')
                box_id = box.get('box_id')
                print(f"[INFO] Unassigning user {user_id} from unassigned box {box_id}")
                if box_service.unassign_user_from_box(user_id):
                    users_unassigned += 1
                    print(f"[SUCCESS] User {user_id} unassigned from box {box_id}")
        
        print(f"[INFO] Unassign all completed: {success_count} screens processed, {users_unassigned} users unassigned, {len(failed_screens)} failures")
        
        if failed_screens:
            return jsonify({
                'message': f'Removed {success_count} screen assignments and unassigned {users_unassigned} users',
                'warning': f'Failed to reset ports: {', '.join(failed_screens)}'
            }), 200
        else:
            return jsonify({
                'message': f'Successfully removed all {success_count} screen assignments and unassigned {users_unassigned} users'
            }), 200
    except Exception as e:
        print(f"[ERROR] Exception in unassign_all: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to remove assignments: {str(e)}'}), 500


@app.route('/screens/disconnect', methods=['POST'])
def disconnect_screen_endpoint():
    """Disconnect a screen (unassign it from any box) and unassign user from box"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': ERROR_REQUEST_BODY_REQUIRED}), 400
    
    screen_id = data.get('screen_id')
    
    if screen_id is None:
        return jsonify({'error': 'screen_id is required'}), 400
    
    # Get screen to reset its port and find the associated box
    screen = screen_service.get_screen_by_id(screen_id)
    if not screen:
        return jsonify({'error': ERROR_SCREEN_NOT_FOUND}), 404
    
    # Get the box_id that was assigned to this screen
    box_id = screen.get('box_id')
    
    # If there's a box assigned, get the user_id and unassign the user from the box
    if box_id:
        box = box_service.get_box_by_id(box_id)
        if box and box.get('user_id'):
            user_id = box.get('user_id')
            print(f"[INFO] Unassigning user {user_id} from box {box_id}")
            box_service.unassign_user_from_box(user_id)
    
    # Unassign screen from box
    result = screen_service.unassign_screen(screen_id)
    if result is None:
        return jsonify({'error': ERROR_SCREEN_NOT_FOUND}), 404
    if result is False:
        return jsonify({'error': ERROR_SCREEN_ALREADY_FREE}), 400
    
    # Reset SCREEN port to default VLAN 101 on switch
    screen_port = screen.get('port_number')
    if screen_port:
        try:
            if cisco_worker.connection and cisco_worker.connection.is_open:
                default_screen_vlan = cisco_worker.default_screen_vlan
                print(f"[INFO] Resetting screen port {screen_port} to default VLAN {default_screen_vlan}")
                cisco_worker.assign_port_to_vlan(screen_port, default_screen_vlan)
        except Exception as e:
            print(f"[ERROR] Error resetting screen port VLAN on switch: {e}")
    
    return jsonify({'message': 'Screen disconnected and user unassigned successfully'}), 200


@app.route('/screens/unassign', methods=['POST'])
def unassign_box_from_screen():
    """Unassign a box from a screen"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': ERROR_REQUEST_BODY_REQUIRED}), 400
    
    box_id = data.get('box_id')
    screen_id = data.get('screen_id')
    
    if box_id is None and screen_id is None:
        return jsonify({'error': 'Either box_id or screen_id is required'}), 400
    
    if box_id is not None:
        # Get box before unassigning to get port info
        box = box_service.get_box_by_id(box_id)
        if not box:
            return jsonify({'error': ERROR_BOX_NOT_FOUND}), 404
        
        # Unassign user from box if one exists
        user_id = box.get('user_id')
        if user_id:
            print(f"[INFO] Unassigning user {user_id} from box {box_id}")
            box_service.unassign_user_from_box(user_id)
        
        # Get screen to reset its port
        screen = screen_service.get_screen_by_box_id(box_id)
        
        # Unassign by box_id
        unassigned = screen_service.unassign_box_from_screen(box_id)
        if not unassigned:
            return jsonify({'error': 'Box has no assigned screen'}), 404
        
        # Reset SCREEN port to default VLAN 101 on switch
        if screen:
            screen_port = screen.get('port_number')
            if screen_port:
                try:
                    if cisco_worker.connection and cisco_worker.connection.is_open:
                        default_screen_vlan = cisco_worker.default_screen_vlan
                        print(f"[INFO] Resetting screen port {screen_port} to default VLAN {default_screen_vlan}")
                        cisco_worker.assign_port_to_vlan(screen_port, default_screen_vlan)
                except Exception as e:
                    print(f"[ERROR] Error resetting screen port VLAN on switch: {e}")
        
        user_msg = f" and user {user_id}" if user_id else ""
        return jsonify({'message': f'Box unassigned from screen{user_msg} successfully'}), 200
    
    if screen_id is not None:
        # Get screen to reset its port
        screen = screen_service.get_screen_by_id(screen_id)
        if not screen:
            return jsonify({'error': ERROR_SCREEN_NOT_FOUND}), 404
        
        box_id_from_screen = screen.get('box_id')
        
        # Unassign user from box if screen is assigned to a box
        user_id = None
        if box_id_from_screen:
            box = box_service.get_box_by_id(box_id_from_screen)
            if box:
                user_id = box.get('user_id')
                if user_id:
                    print(f"[INFO] Unassigning user {user_id} from box {box_id_from_screen}")
                    box_service.unassign_user_from_box(user_id)
        
        # Unassign by screen_id
        result = screen_service.unassign_screen(screen_id)
        if result is None:
            return jsonify({'error': ERROR_SCREEN_NOT_FOUND}), 404
        if result is False:
            return jsonify({'error': ERROR_SCREEN_ALREADY_FREE}), 400
        
        # Reset SCREEN port to default VLAN 101 on switch
        screen_port = screen.get('port_number')
        if screen_port:
            try:
                if cisco_worker.connection and cisco_worker.connection.is_open:
                    default_screen_vlan = cisco_worker.default_screen_vlan
                    print(f"[INFO] Resetting screen port {screen_port} to default VLAN {default_screen_vlan}")
                    cisco_worker.assign_port_to_vlan(screen_port, default_screen_vlan)
            except Exception as e:
                print(f"[ERROR] Error resetting screen port VLAN on switch: {e}")
        
        user_msg = f" and user {user_id}" if user_id else ""
        return jsonify({'message': f'Screen unassigned{user_msg} successfully'}), 200


@app.route('/screens/box/<int:box_id>', methods=['GET'])
def get_screen_by_box(box_id):
    """Get screen assigned to a specific box"""
    screen = screen_service.get_screen_by_box_id(box_id)
    
    if not screen:
        return jsonify({'has_screen': False}), 200
    
    return jsonify({
        'has_screen': True,
        'screen': screen
    }), 200


@app.route('/screens/user/<user_id>', methods=['GET'])
def get_user_screen(user_id):
    """Get screen assigned to a specific user (through their box)"""
    # First get the user's box
    box = box_service.get_box_by_user_id(user_id)
    
    if not box:
        return jsonify({
            'has_box': False,
            'has_screen': False
        }), 200
    
    # Then get the screen for that box
    screen = screen_service.get_screen_by_box_id(box['box_id'])
    
    if not screen:
        return jsonify({
            'has_box': True,
            'has_screen': False,
            'box_id': box['box_id'],
            'box_number': box.get('box_number', ''),
            'user_id': user_id
        }), 200
    
    return jsonify({
        'has_box': True,
        'has_screen': True,
        'user_id': user_id,
        'box_id': box['box_id'],
        'box_number': box.get('box_number', ''),
        'box_port_number': box.get('port_number'),
        'box_vlan_number': box.get('vlan_number'),
        'screen_id': screen['screen_id'],
        'screen_number': screen.get('screen_number'),
        'screen_port_number': screen.get('port_number'),
        'screen_vlan_number': screen.get('vlan_number')
    }), 200


@app.route('/screens/<int:screen_id>', methods=['PUT', 'PATCH'])
def update_screen(screen_id):
    """Update screen attributes"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': ERROR_REQUEST_BODY_REQUIRED}), 400
    
    # Extract updatable fields
    screen_number = data.get('screen_number')
    port_number = data.get('port_number')
    vlan_number = data.get('vlan_number')
    
    # Check if at least one field is provided
    if screen_number is None and port_number is None and vlan_number is None:
        return jsonify({'error': 'At least one field (screen_number, port_number, or vlan_number) must be provided'}), 400
    
    # Update the screen
    updated_screen = screen_service.update_screen(screen_id, screen_number=screen_number, port_number=port_number, vlan_number=vlan_number)
    
    if not updated_screen:
        return jsonify({'error': ERROR_SCREEN_NOT_FOUND}), 404
    
    return jsonify(updated_screen), 200


# Cisco switch endpoints

@app.route('/switch/info', methods=['GET'])
def get_switch_info():
    """Get comprehensive switch information"""
    try:
        info = cisco_worker.get_switch_info()
        return jsonify(info), 200
    except Exception as e:
        return jsonify({'error': f'Failed to get switch info: {str(e)}'}), 500


@app.route('/switch/ports', methods=['GET'])
def get_all_ports():
    """Get status of all ports on the switch"""
    try:
        ports = cisco_worker.get_all_ports_status()
        return jsonify(ports), 200
    except Exception as e:
        return jsonify({'error': f'Failed to get ports status: {str(e)}'}), 500


@app.route('/switch/ports_vlans', methods=['GET'])
def get_all_ports_vlans():
    """Get VLAN configuration for all ports from the switch"""
    try:
        print("[INFO] Getting VLANs for all ports from switch...")
        if not cisco_worker.connection or not cisco_worker.connection.is_open:
            print("[ERROR] Switch not connected")
            return jsonify({'error': 'Switch not connected'}), 500
        
        # Get all boxes and screens
        boxes = box_service.get_all_boxes()
        screens = screen_service.get_all_screens()
        
        result = {
            'boxes': {},
            'screens': {}
        }
        
        # Get actual VLANs for boxes
        for box in boxes:
            port = box.get('port_number')
            box_id = box.get('box_id')
            if port:
                print(f"[DEBUG] Getting VLAN for box {box_id} port {port}")
                vlan = cisco_worker.get_port_vlan(port)
                result['boxes'][box_id] = vlan
                print(f"[DEBUG] Box {box_id} port {port} VLAN: {vlan}")
        
        # Get actual VLANs for screens
        for screen in screens:
            port = screen.get('port_number')
            screen_id = screen.get('screen_id')
            if port:
                print(f"[DEBUG] Getting VLAN for screen {screen_id} port {port}")
                vlan = cisco_worker.get_port_vlan(port)
                result['screens'][screen_id] = vlan
                print(f"[DEBUG] Screen {screen_id} port {port} VLAN: {vlan}")
        
        print(f"[SUCCESS] Retrieved VLANs for {len(result['boxes'])} boxes and {len(result['screens'])} screens")
        return jsonify(result), 200
    except Exception as e:
        print(f"[ERROR] Failed to get ports VLANs: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to get ports VLANs: {str(e)}'}), 500


@app.route('/switch/reconfigure_port', methods=['POST'])
def reconfigure_port():
    """Reconfigure a specific port to a target VLAN"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': ERROR_REQUEST_BODY_REQUIRED}), 400
        
        port = data.get('port')
        vlan = data.get('vlan')
        
        if not port or not vlan:
            return jsonify({'error': 'Both port and vlan are required'}), 400
        
        print(f"[INFO] Reconfiguring port {port} to VLAN {vlan}")
        
        if not cisco_worker.connection or not cisco_worker.connection.is_open:
            print("[ERROR] Switch not connected")
            return jsonify({'error': 'Switch not connected'}), 500
        
        success = cisco_worker.assign_port_to_vlan(port, vlan)
        
        if success:
            print(f"[SUCCESS] Port {port} reconfigured to VLAN {vlan}")
            return jsonify({'message': f'Port {port} successfully reconfigured to VLAN {vlan}'}), 200
        else:
            print(f"[ERROR] Failed to reconfigure port {port} to VLAN {vlan}")
            return jsonify({'error': f'Failed to reconfigure port {port}'}), 500
    except Exception as e:
        print(f"[ERROR] Exception in reconfigure_port: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to reconfigure port: {str(e)}'}), 500


@app.route('/switch/ports/<path:port>', methods=['GET'])
def get_port_status(port):
    """Get status of a specific port"""
    try:
        status = cisco_worker.get_port_status(port)
        return jsonify(status), 200
    except Exception as e:
        return jsonify({'error': f'Failed to get port status: {str(e)}'}), 500


@app.route('/switch/sync', methods=['POST'])
def sync_switch():
    """Manually trigger switch synchronization with database"""
    try:
        success = cisco_worker.sync_with_db()
        if success:
            return jsonify({'message': 'Switch synchronized successfully'}), 200
        else:
            return jsonify({'error': 'Failed to synchronize switch'}), 500
    except Exception as e:
        return jsonify({'error': f'Failed to sync switch: {str(e)}'}), 500


@app.route('/screens/reset_all_vlans', methods=['POST'])
def reset_all_screen_vlans():
    """Reset all screen ports to default VLAN 101"""
    try:
        print("[INFO] Starting reset_all_screen_vlans operation...")
        
        if not cisco_worker.connection or not cisco_worker.connection.is_open:
            print("[ERROR] Switch not connected")
            return jsonify({'error': 'Switch not connected'}), 500
        
        # Get all screens
        screens = screen_service.get_all_screens()
        if not screens:
            print("[INFO] No screens found")
            return jsonify({'message': 'No screens found'}), 200
        
        print(f"[INFO] Found {len(screens)} screens to reset")
        default_vlan = cisco_worker.default_screen_vlan
        print(f"[INFO] Default screen VLAN: {default_vlan}")
        
        success_count = 0
        failed_ports = []
        
        for idx, screen in enumerate(screens, 1):
            screen_port = screen.get('port_number')
            screen_id = screen.get('screen_id')
            if screen_port:
                print(f"[INFO] Processing screen {idx}/{len(screens)}: ID={screen_id}, Port={screen_port}")
                success = cisco_worker.assign_port_to_vlan(screen_port, default_vlan)
                if success:
                    success_count += 1
                    print(f"[SUCCESS] Screen {screen_id} port {screen_port} reset successfully ({success_count}/{len(screens)})")
                else:
                    failed_ports.append(screen_port)
                    print(f"[ERROR] Failed to reset screen {screen_id} port {screen_port}")
            else:
                print(f"[WARNING] Screen {screen_id} has no port number")
        
        print(f"[INFO] Reset operation completed: {success_count} successful, {len(failed_ports)} failed")
        
        if failed_ports:
            return jsonify({
                'message': f'Reset {success_count} screens to VLAN {default_vlan}',
                'warning': f'Failed to reset ports: {", ".join(failed_ports)}'
            }), 200
        else:
            return jsonify({
                'message': f'Successfully reset all {success_count} screens to VLAN {default_vlan}'
            }), 200
    except Exception as e:
        print(f"[ERROR] Exception in reset_all_screen_vlans: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to reset screen VLANs: {str(e)}'}), 500


@app.route('/switch/connect', methods=['POST'])
def connect_switch():
    """Connect to the switch"""
    try:
        success = cisco_worker.connect()
        if success:
            return jsonify({'message': 'Connected to switch successfully'}), 200
        else:
            return jsonify({'error': 'Failed to connect to switch'}), 500
    except Exception as e:
        return jsonify({'error': f'Failed to connect: {str(e)}'}), 500


@app.route('/switch/disconnect', methods=['POST'])
def disconnect_switch():
    """Disconnect from the switch"""
    try:
        cisco_worker.disconnect()
        return jsonify({'message': 'Disconnected from switch successfully'}), 200
    except Exception as e:
        return jsonify({'error': f'Failed to disconnect: {str(e)}'}), 500


@app.route('/config/serial_port', methods=['GET'])
def get_serial_port():
    """Get the configured serial port"""
    try:
        serial_port = config_service.get_serial_port()
        return jsonify({'serial_port': serial_port}), 200
    except Exception as e:
        return jsonify({'error': f'Failed to get serial port: {str(e)}'}), 500


@app.route('/config/serial_port', methods=['PUT', 'POST'])
def set_serial_port():
    """Set the serial port configuration"""
    try:
        data = request.get_json()
        if not data or 'serial_port' not in data:
            return jsonify({'error': 'serial_port is required'}), 400
        
        serial_port = data['serial_port']
        
        # Update configuration in database
        config_service.set_serial_port(serial_port)
        
        # Disconnect current connection if exists
        if cisco_worker.connection and cisco_worker.connection.is_open:
            cisco_worker.disconnect()
        
        # Update worker with new port
        cisco_worker.serial_port = serial_port
        
        return jsonify({
            'message': 'Serial port updated successfully',
            'serial_port': serial_port
        }), 200
    except Exception as e:
        return jsonify({'error': f'Failed to set serial port: {str(e)}'}), 500


@app.route('/config', methods=['GET'])
def get_all_config():
    """Get all configuration values"""
    try:
        config = config_service.get_all_config()
        return jsonify(config), 200
    except Exception as e:
        return jsonify({'error': f'Failed to get configuration: {str(e)}'}), 500


def initialize_switch():
    """Initialize switch connection and sync with DB on server startup"""
    try:
        print("Connecting to Cisco switch...")
        if cisco_worker.connect():
            print("Connected to switch, entering enable mode...")
            if cisco_worker.enable_mode():
                print("Synchronizing switch with database...")
                if cisco_worker.sync_with_db():
                    print("Switch synchronized successfully")
                else:
                    print("Warning: Failed to synchronize switch with database")
            else:
                print("Warning: Failed to enter enable mode")
        else:
            print("Warning: Failed to connect to switch. Switch operations will be unavailable.")
    except Exception as e:
        print(f"Error initializing switch: {e}")


if __name__ == '__main__':
    # Initialize switch on startup
    initialize_switch()
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)

