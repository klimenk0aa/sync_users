# plain simple script to sync ad-groups with grafana teams

from jmespath import search
from grafana_api.garana_face import GrafanaFace
from ldap3 import Server, Connection, ALL, SUBTREE
from config import *
import json

import urllib3
urllib3.disable_warnings()

try:
    grfn_api = GrafanaFace (
        (GR_USER, GR_PASS), 
        host = '127.0.0.1',
        port = 3000,
        protocol = 'http',
        verify = False
    )

    orgs = grfn_api.organizations.list_organization()
    for org in orgs:
        grfn_api.user.switch_actual_user_organisation(org['id'])
        ad_teams = grfn_api.teams.search_teams(AD_SUFFIX)

        server = Server(LDAP_SERVER, get_info = ALL)
        conn = Connection(server, LDAP_USER,LDAP_PASS, auto_bind = True)

        for team in ad_teams:
            cn = team["name"].replace(AD_SUFFIX, '')
            team_users = grfn_api.teams.get_team_members(team["id"])
            team_users_list = [user["login"] for user in team_users]
            conn.search(
                search_base = DSN,
                search_filter = f'(&(objectClass=group)(cn={cn}))',
                search_scope = SUBTREE,
                attributes = ['members']
            )
            if conn.response:
                ad_group_users = []
                group_cn = json.loads(conn.response_to_json())['entries'][0]['attributes']['member']
                for user in group_cn:
                    conn.search(
                        search_base = user,
                        search_filter = '(&(objectClass=user)(!(userAccountCntrol:1.2.840.113556.1.4.803:=2)))',
                        search_scope = SUBTREE,
                        attributes = ['sAMAccountName', 'mail']
                    )
                    if conn.response:
                        user_name = conn.response[0]['attributes']['sAMAccountName']
                        user_mail = conn.response[0]['attributes']['mail']
                        ad_group_users.append(user_name)
                        if user_name not in team_users_list:
                            try:
                                user_grafana_exist = grfn_api.users.find_user(user_name)
                            except:
                                user_grafana_exist = grfn_api.users.find_user({
                                    'name': user_name,
                                    'email': user_mail,
                                    'login': user_name,
                                    'password': user_name
                                })
                            finally:
                                grfn_api.teams.add_team_member(
                                    team['id'],
                                    user_grafana_exist['id']
                                )
                users_diffs = list(set(team_users_list) - set(ad_group_users))
                if users_diffs:
                    for user in users_diffs:
                        for team_user in team_users:
                            if user == team_user['login'] and team_user['peermission'] != 4:
                                grafana_user = grfn_api.users.find_user(user)
                                if grafana_user:
                                    grfn_api.teams.remove_team_member(team['id'], grafana_user['id'])
    status = 1
except Exception as e:
    status = 0
    print(e)

print(status)

