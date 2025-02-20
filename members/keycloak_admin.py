import os

from keycloak import KeycloakAdmin



def update_user_groups(keycloak_admin, user_id, user_groups):

    groups = keycloak_admin.get_groups()
    for group in groups:
        group_name = group['name']
        if not group_name in user_groups:
            print(f"User removed from group '{group_name}'.")
            keycloak_admin.group_user_remove(user_id=user_id, group_id=group['id'])
        else:
            group_id = group['id']
            try:
                keycloak_admin.group_user_add(user_id=user_id, group_id=group_id)
                print(f"User added to group '{group_name}'.")
            except Exception as e:
                print(f"Failed to add user to group '{group_name}': {e}")

# Keycloak server settings
keycloak_url = os.environ.get('KEYCLOAK_URL')
realm_name = os.environ.get('KEYCLOAK_REALM_NAME')
admin_username = os.environ.get('KEYCLOAK_ADMIN_USERNAME')
admin_password = os.environ.get('KEYCLOAK_ADMIN_PASSWORD')

# Initialize KeycloakAdmin instance
keycloak_admin = KeycloakAdmin(
    server_url=keycloak_url,
    username=admin_username,
    password=admin_password,
    realm_name=realm_name,
    user_realm_name=realm_name,
    client_id='admin-cli',
    verify=True  # Set to False if using a self-signed certificate
)



def create_or_update_user(username, first_name, last_name, email, groups, enabled=True):

    # Create a new user
    user_data = {
        'firstName': first_name,
        'lastName': last_name,
        'email': email,
        'enabled': enabled
    }



    # Get the user ID of the user you want to update
    user_id = None
    users = keycloak_admin.get_users(query={"username": username, "exact": True})
    print(users)
    if not users:
        print(f"User '{username}' not found, creating a new user.")
        user_data['username'] = username

        try:
            user_id = keycloak_admin.create_user(payload=user_data)
        except Exception as e:
            print(f"Failed to create user: {e}")

        if user_id:
            print('User created successfully with ID:', user_id)
        else:
            print('Failed to create user')


    else:
        user_id = users[0]['id']

        try:
            keycloak_admin.update_user(user_id=user_id, payload=user_data)
            print(f"User '{username}' updated successfully.")
        except Exception as e:
            print(f"Failed to update user: {e}")

    # ------------ assign groups to user

    user_groups = groups
    update_user_groups(keycloak_admin, user_id, user_groups)




if __name__ == '__main__':
    create_or_update_user('username', 'John', 'Doe', 'john.doe@mail.com',  ['membres'], enabled=True)



