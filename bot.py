import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
import os
import json
import asyncio
from threading import Thread
from flask import Flask
from datetime import datetime, timedelta
import io

app = Flask('')

@app.route('/')
def home(): return "Le bot Valerius est vivant !"

def run_web(): app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = Thread(target=run_web)
    t.start()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

PROPRIETAIRE_LOGS_NOM = "MAVIE7620"
WELCOME_CHANNEL_ID = 1534604841660190792
ATTENTE_MOOV_ID = 1534604587992875280
SALON_PALAIS_ROYAL_ID = 1519322938430722129

def get_file_name(guild_id):
    return f"valerius_missions_{guild_id}.txt"

def get_profiles_file(guild_id):
    return f"valerius_profils_{guild_id}.json"

def get_active_missions_file(guild_id):
    return f"valerius_missions_actives_{guild_id}.json"

def charger_missions_fichier(guild_id):
    structure = {"commune": [], "moyenne": [], "difficile": [], "royal": []}
    file_name = get_file_name(guild_id)
    if not os.path.exists(file_name): return structure
    with open(file_name, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or "|" not in line: continue
            cat, texte, delai = line.split("|", 2)
            if cat in structure: structure[cat].append({"texte": texte, "delai": delai})
    return structure

def réécrire_toutes_missions(guild_id, structure):
    file_name = get_file_name(guild_id)
    with open(file_name, "w", encoding="utf-8") as f:
        for cat, liste in structure.items():
            for m in liste: f.write(f"{cat}|{m['texte']}|{m['delai']}\n")

def sauvegarder_mission_fichier(guild_id, categorie, texte, delai):
    file_name = get_file_name(guild_id)
    with open(file_name, "a", encoding="utf-8") as f: f.write(f"{categorie}|{texte}|{delai}\n")

def vider_toutes_missions(guild_id):
    file_name = get_file_name(guild_id)
    with open(file_name, "w", encoding="utf-8") as f:
        f.write("")

def charger_profils(guild_id):
    profiles_file = get_profiles_file(guild_id)
    if not os.path.exists(profiles_file): return {}
    try:
        with open(profiles_file, "r", encoding="utf-8") as f: return json.load(f)
    except: return {}

def sauvegarder_profils(guild_id, profils):
    profiles_file = get_profiles_file(guild_id)
    with open(profiles_file, "w", encoding="utf-8") as f: json.dump(profils, f, indent=4, ensure_ascii=False)

def initialiser_profil(p_id, profils):
    s_id = str(p_id)
    if s_id not in profils:
        profils[s_id] = {
            "total_reussies": 0,
            "total_echouees": 0,
            "historique": []
        }

def ajouter_historique(p_id, profils, texte, statut):
    s_id = str(p_id)
    initialiser_profil(p_id, profils)
    profils[s_id]["historique"].insert(0, {
        "texte": texte,
        "statut": statut,
        "date": datetime.now().strftime("%d/%m/%Y à %H:%M")
    })

def extraire_duree(delai_texte):
    mots = delai_texte.lower().replace("pour dans", "").replace("pour", "").strip().split()
    valeur = 1
    for i, mot in enumerate(mots):
        try: valeur = float(mots[i-1].replace(",", "."))
        except (ValueError, IndexError): continue
        if "min" in mot or "mn" in mot: return timedelta(minutes=valeur)
        if "heure" in mot or "hour" in mot or "h" in mot: return timedelta(hours=valeur)
        if "jour" in mot or "day" in mot or "j" in mot: return timedelta(days=valeur)
        if "semaine" in mot or "week" in mot: return timedelta(weeks=valeur)
        if "mois" in mot or "moi" in mot or "month" in mot: return timedelta(days=valeur * 30)
    return timedelta(days=3)

missions_actives = {}

TEXTE_ECHEC = (
    "⚜️ **𝕾𝖞𝖘𝖙𝖊̀𝖒𝖊 𝖉𝖊 𝕸𝖎𝖘𝖘𝖎𝖔𝖓𝖘 𝖉𝖊 𝕁𝖆𝖑𝖊𝖗𝖎𝖚𝖘** ⚜️\n"
    "**D'après l'article Ⅴ — Rappel :**\n"
    "- **Refuser ou abandonner une mission attribuée sans raison valable peut être sanctionné.**\n"
    "- *L'État récompense l'investissement et la persévérance.*\n"
    "- *Les missions constituent l'un des principaux moyens de progresser au sein de Valerius.*"
)

def verifier_permissions_staff(user):
    roles_noms = [r.name for r in user.roles]
    return user.guild_permissions.administrator or "[ 𝔦𝔫𝔰𝔱𝔯𝔲𝔠𝖙𝔢𝖚🇷 ]" in roles_noms or "[ Palais Royal ]" in roles_noms or "Palais Royal" in roles_noms or any(r.permissions.manage_channels or r.permissions.administrator for r in user.roles)

async def envoyer_log_proprietaire(bot_instance, texte_log, view=None, guild_target=None, joueur_id_target=None):
    for guild in bot_instance.guilds:
        membre = discord.utils.get(guild.members, name=PROPRIETAIRE_LOGS_NOM)
        if not membre:
            membre = discord.utils.get(guild.members, global_name=PROPRIETAIRE_LOGS_NOM)
        if membre:
            try:
                v = view(guild_target, joueur_id_target) if (view and guild_target and joueur_id_target) else view
                await membre.send(f"📋 **[LOG GLOBAL ABSOLU - VALERIUS]** : {texte_log}", view=v)
                return
            except Exception as e:
                pass
    print(f"[LOG GLOBAL ABSOLU CONSOLE] {texte_log}")

async def envoyer_double_notification(guild, msg_ticket, msg_missions, view=None, joueur_id=None):
    salon_missions = discord.utils.get(guild.text_channels, name="validation-mission")
    if salon_missions:
        try: await salon_missions.send(msg_missions, view=view(joueur_id) if view and joueur_id else view)
        except: pass
    
    await envoyer_log_proprietaire(guild._state._get_client(), f"[{guild.name}] {msg_missions}", view=VueEvaluationMissionMP if view else None, guild_target=guild, joueur_id_target=joueur_id)

class VueFermerTicket(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔒 Fermer le ticket", style=discord.ButtonStyle.danger, custom_id="btn_fermer_ticket")
    async def fermer_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await envoyer_log_proprietaire(bot, f"LOG ABSOLU - Clic bouton Fermer le ticket par {interaction.user.name} dans {interaction.channel.name} ({interaction.guild.name})")
        await interaction.response.send_message("⚙️ Suppression du salon en cours...", ephemeral=True)
        
        g_id = interaction.guild.id
        if g_id in missions_actives:
            for j_id, m_info in list(missions_actives[g_id].items()):
                if m_info.get("channel_id") == interaction.channel.id or f"🪖-ordre-" in interaction.channel.name:
                    member = interaction.guild.get_member(j_id)
                    if member and member.name.lower() in interaction.channel.name.lower():
                        del missions_actives[g_id][j_id]
                        break

        try: await interaction.channel.delete()
        except: pass

class VueButinRecupere(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📦 Butin récupéré", style=discord.ButtonStyle.primary, custom_id="btn_butin_recupere")
    async def butin_recupere(self, interaction: discord.Interaction, button: discord.ui.Button):
        await envoyer_log_proprietaire(bot, f"LOG ABSOLU - Clic bouton Butin récupéré par {interaction.user.name} dans {interaction.channel.name} ({interaction.guild.name})")
        for child in self.children:
            child.disabled = True
        try:
            await interaction.response.edit_message(view=self)
        except:
            pass
        await interaction.channel.send("✅ **Le butin a été récupéré avec succès par l'instructeur.**", view=VueFermerTicket())

class VueAccueilArrivant(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="👑 Je suis greyjoy", style=discord.ButtonStyle.danger, custom_id="btn_greyjoy")
    async def greyjoy_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        role_palais = discord.utils.get(interaction.guild.roles, name="[ Palais Royal ]") or discord.utils.get(interaction.guild.roles, name="Palais Royal")
        salon_cible = interaction.guild.get_channel(SALON_PALAIS_ROYAL_ID)
        
        mention_role = role_palais.mention if role_palais else "@[ Palais Royal ]"
        
        if salon_cible:
            try:
                await salon_cible.send(f"🚨 {mention_role} ! Un membre s'identifie en tant que Greyjoy.")
                await interaction.response.send_message(f"✅ Un haut gradé a été prévenu dans le salon {salon_cible.mention} !", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ Erreur lors de l'envoi du message dans le salon dédié : {e}", ephemeral=True)
        else:
            await interaction.response.send_message(f"🚨 Un haut gradé a été ping : {mention_role} ! Un membre s'identifie en tant que Greyjoy. (Salon cible introuvable par ID)", ephemeral=True)

    @discord.ui.button(label="👤 Je suis un visiteurs", style=discord.ButtonStyle.secondary, custom_id="btn_visiteur")
    async def visiteur_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        role_etranger = discord.utils.get(interaction.guild.roles, name="[💥] Etranger [💥]") or discord.utils.get(interaction.guild.roles, name="etranger")
        if role_etranger:
            try:
                await interaction.user.add_roles(role_etranger)
                await interaction.response.send_message(f"✅ Rôle **{role_etranger.name}** attribué avec succès !", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ Erreur lors de l'attribution du rôle : {e}", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Le rôle `[💥] Etranger [💥]` est introuvable sur ce serveur. Contactez un admin.", ephemeral=True)

    @discord.ui.button(label="⚔️ Je souhaite etre recruter", style=discord.ButtonStyle.success, custom_id="btn_recrutement")
    async def recrutement_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        role_recrutement = discord.utils.get(interaction.guild.roles, name="en cours de recrutement")
        salon_attente = interaction.guild.get_channel(ATTENTE_MOOV_ID) or discord.utils.get(interaction.guild.text_channels, name="attente-moov")
        
        if not role_recrutement:
            await interaction.response.send_message("❌ Le rôle `en cours de recrutement` est introuvable sur ce serveur.", ephemeral=True)
            return

        try:
            await interaction.user.add_roles(role_recrutement)
            
            if salon_attente:
                await salon_attente.set_permissions(interaction.user, read_messages=True, send_messages=True, connect=True)
                await interaction.response.send_message(f"✅ Tu as obtenu le rôle **en cours de recrutement** et l'accès au salon {salon_attente.mention} !", ephemeral=True)
            else:
                await interaction.response.send_message("✅ Rôle attribué, mais le salon `attente moov` est introuvable avec cet ID.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Une erreur est survenue : {e}", ephemeral=True)

class VueGestionJoueurMission(discord.ui.View):
    def __init__(self, joueur_id=None):
        super().__init__(timeout=None)
        self.joueur_id = joueur_id

    @discord.ui.button(label="🏁 Finir la mission", style=discord.ButtonStyle.success, custom_id="joueur_finir_mission")
    async def joueur_finir(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Récupération dynamique du joueur si relancé après redémarrage
        g_id = interaction.guild.id
        current_joueur_id = self.joueur_id
        if not current_joueur_id and g_id in missions_actives:
            for j_id, m_info in missions_actives[g_id].items():
                if m_info.get("channel_id") == interaction.channel.id:
                    current_joueur_id = j_id
                    break

        if current_joueur_id and interaction.user.id != current_joueur_id and not verifier_permissions_staff(interaction.user):
            await interaction.response.send_message("❌ Cet objectif ne t'appartient pas.", ephemeral=True)
            return

        target_id = current_joueur_id if current_joueur_id else interaction.user.id
        if g_id not in missions_actives or target_id not in missions_actives[g_id]:
            await interaction.response.send_message("❌ Tu n'as aucune mission active sur ce serveur.", ephemeral=True)
            return

        m_info = missions_actives[g_id][target_id]
        if not m_info.get("en_attente", False):
            m_info["en_attente"] = True
            m_info["moment_gel"] = datetime.now()

        for child in self.children: child.disabled = True
        try:
            await interaction.response.edit_message(view=self)
        except:
            await interaction.response.defer(ephemeral=True)

        role_instructeur = discord.utils.get(interaction.guild.roles, name="[ 𝔦𝔫𝔰𝔱𝔯𝔲𝔠𝖙𝔢𝖚🇷 ]")
        mention_ins = role_instructeur.mention if role_instructeur else '@[ 𝔦𝔫𝔰𝔱𝔯𝔲𝔠𝖙𝔢𝖚🇷 ]'

        member_obj = interaction.guild.get_member(target_id)
        if member_obj:
            await interaction.channel.set_permissions(member_obj, read_messages=True, send_messages=False)
        
        await interaction.channel.send(f"💬 <@{target_id>>, un instructeur a été notifié. Votre demande va être traitée dans les plus brefs délais.")
        
        msg_fin = (
            f"📢 {mention_ins} ! <@{target_id}> déclare avoir fini sa mission via l'interface : *\"{m_info['texte']}\"* !\n"
            f"⏱️ **Le chrono est mis en pause.** Choisissez l'action appropriée :"
        )
        await envoyer_double_notification(interaction.guild, msg_fin, f"📢 {mention_ins} — <@{target_id}> demande une validation pour : *\"{m_info['texte']}\"* dans {interaction.channel.mention}", view=VueEvaluationMission, joueur_id=target_id)
        await envoyer_log_proprietaire(bot, f"LOG ABSOLU - JOUEUR FINIR : {interaction.user.name} a cliqué Finir la mission sur {interaction.guild.name}")

    @discord.ui.button(label="❌ Abandonner", style=discord.ButtonStyle.danger, custom_id="joueur_abandonner_mission")
    async def joueur_abandonner(self, interaction: discord.Interaction, button: discord.ui.Button):
        g_id = interaction.guild.id
        current_joueur_id = self.joueur_id
        if not current_joueur_id and g_id in missions_actives:
            for j_id, m_info in missions_actives[g_id].items():
                if m_info.get("channel_id") == interaction.channel.id:
                    current_joueur_id = j_id
                    break

        target_id = current_joueur_id if current_joueur_id else interaction.user.id
        if current_joueur_id and interaction.user.id != current_joueur_id and not verifier_permissions_staff(interaction.user):
            await interaction.response.send_message("❌ Tu ne peux pas abandonner la mission de quelqu'un d'autre.", ephemeral=True)
            return

        if g_id not in missions_actives or target_id not in missions_actives[g_id]:
            await interaction.response.send_message("❌ Tu n'as pas de mission active à abandonner sur ce serveur.", ephemeral=True)
            return

        for child in self.children: child.disabled = True
        try:
            await interaction.response.edit_message(view=self)
        except:
            await interaction.response.defer(ephemeral=True)
            
        await action_refuser_mission(target_id, interaction.channel)
        await envoyer_log_proprietaire(bot, f"LOG ABSOLU - JOUEUR ABANDONNER : {interaction.user.name} a abandonné sa mission sur {interaction.guild.name}")

class VueEvaluationMission(discord.ui.View):
    def __init__(self, joueur_id=None):
        super().__init__(timeout=None)
        self.joueur_id = joueur_id

    @discord.ui.button(label="✅ Accepter", style=discord.ButtonStyle.success, custom_id="eval_accepter")
    async def eval_accepter(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not verifier_permissions_staff(interaction.user):
            await interaction.response.send_message("❌ Tu n'as pas l'autorité nécessaire pour évaluer cet ordre.", ephemeral=True)
            return
        
        for child in self.children: child.disabled = True
        try: await interaction.response.edit_message(view=self)
        except: pass
        
        target_j_id = self.joueur_id
        g_id = interaction.guild.id
        if not target_j_id and g_id in missions_actives:
            for j_id, m_info in missions_actives[g_id].items():
                if m_info.get("channel_id") == interaction.channel.id:
                    target_j_id = j_id
                    break

        chan_cible = interaction.channel
        if target_j_id and g_id in missions_actives and target_j_id in missions_actives[g_id]:
            c = bot.get_channel(missions_actives[g_id][target_j_id]["channel_id"])
            if c: chan_cible = c

        if target_j_id:
            await action_accepter_mission(target_j_id, chan_cible)
        else:
            await interaction.followup.send("❌ Impossible de lier cette évaluation à un joueur actif.", ephemeral=True)

    @discord.ui.button(label="❌ Refuser", style=discord.ButtonStyle.danger, custom_id="eval_refuser")
    async def eval_refuser(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not verifier_permissions_staff(interaction.user):
            await interaction.response.send_message("❌ Tu n'as pas l'autorité nécessaire pour évaluer cet ordre.", ephemeral=True)
            return
        
        for child in self.children: child.disabled = True
        try: await interaction.response.edit_message(view=self)
        except: pass
        
        target_j_id = self.joueur_id
        g_id = interaction.guild.id
        if not target_j_id and g_id in missions_actives:
            for j_id, m_info in missions_actives[g_id].items():
                if m_info.get("channel_id") == interaction.channel.id:
                    target_j_id = j_id
                    break

        chan_cible = interaction.channel
        if target_j_id and g_id in missions_actives and target_j_id in missions_actives[g_id]:
            c = bot.get_channel(missions_actives[g_id][target_j_id]["channel_id"])
            if c: chan_cible = c

        if target_j_id:
            await action_refuser_mission(target_j_id, chan_cible)
        else:
            await interaction.followup.send("❌ Impossible de lier cette évaluation à un joueur actif.", ephemeral=True)

    @discord.ui.button(label="📸 Demander des preuves", style=discord.ButtonStyle.primary, custom_id="eval_preuve")
    async def eval_preuve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not verifier_permissions_staff(interaction.user):
            await interaction.response.send_message("❌ Tu n'as pas l'autorité nécessaire.", ephemeral=True)
            return

        for child in self.children: child.disabled = True
        try: await interaction.response.edit_message(view=self)
        except: pass
        
        target_j_id = self.joueur_id
        target_guild = interaction.guild
        g_id = interaction.guild.id
        if not target_j_id and g_id in missions_actives:
            for j_id, m_info in missions_actives[g_id].items():
                if m_info.get("channel_id") == interaction.channel.id:
                    target_j_id = j_id
                    break

        chan_cible = interaction.channel
        if target_j_id and g_id in missions_actives and target_j_id in missions_actives[g_id]:
            c = bot.get_channel(missions_actives[g_id][target_j_id]["channel_id"])
            if c: chan_cible = c

        if target_j_id:
            await action_demander_preuve(target_j_id, chan_cible, target_guild)
        else:
            await interaction.followup.send("❌ Impossible de lier cette demande à un joueur actif.", ephemeral=True)

class VueEvaluationMissionMP(discord.ui.View):
    def __init__(self, guild_target, joueur_id):
        super().__init__(timeout=None)
        self.guild_target = guild_target
        self.joueur_id = joueur_id

    @discord.ui.button(label="✅ Accepter (MP)", style=discord.ButtonStyle.success, custom_id="eval_mp_accepter")
    async def eval_mp_accepter(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children: child.disabled = True
        try: await interaction.response.edit_message(view=self)
        except: pass

        chan_cible = None
        if self.guild_target and self.guild_target.id in missions_actives and self.joueur_id in missions_actives[self.guild_target.id]:
            chan_cible = bot.get_channel(missions_actives[self.guild_target.id][self.joueur_id]["channel_id"])
        if not chan_cible and self.guild_target:
            chan_cible = discord.utils.get(self.guild_target.text_channels, name="validation-mission")
        
        if chan_cible:
            await action_accepter_mission(self.joueur_id, chan_cible)
            await interaction.followup.send("✅ Mission acceptée avec succès depuis les logs !", ephemeral=True)
        else:
            await interaction.followup.send("❌ Salon introuvable pour cette mission.", ephemeral=True)

    @discord.ui.button(label="❌ Refuser (MP)", style=discord.ButtonStyle.danger, custom_id="eval_mp_refuser")
    async def eval_mp_refuser(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children: child.disabled = True
        try: await interaction.response.edit_message(view=self)
        except: pass

        chan_cible = None
        if self.guild_target and self.guild_target.id in missions_actives and self.joueur_id in missions_actives[self.guild_target.id]:
            chan_cible = bot.get_channel(missions_actives[self.guild_target.id][self.joueur_id]["channel_id"])
        if not chan_cible and self.guild_target:
            chan_cible = discord.utils.get(self.guild_target.text_channels, name="validation-mission")
        
        if chan_cible:
            await action_refuser_mission(self.joueur_id, chan_cible)
            await interaction.followup.send("❌ Mission refusée depuis les logs.", ephemeral=True)
        else:
            await interaction.followup.send("❌ Salon introuvable pour cette mission.", ephemeral=True)

    @discord.ui.button(label="📸 Preuve (MP)", style=discord.ButtonStyle.primary, custom_id="eval_mp_preuve")
    async def eval_mp_preuve(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children: child.disabled = True
        try: await interaction.response.edit_message(view=self)
        except: pass

        chan_cible = None
        if self.guild_target and self.guild_target.id in missions_actives and self.joueur_id in missions_actives[self.guild_target.id]:
            chan_cible = bot.get_channel(missions_actives[self.guild_target.id][self.joueur_id]["channel_id"])
        
        if chan_cible and self.guild_target:
            await action_demander_preuve(self.joueur_id, chan_cible, self.guild_target)
            await interaction.followup.send("📸 Demande de preuve transmise depuis les logs.", ephemeral=True)
        else:
            await interaction.followup.send("❌ Salon introuvable pour cette mission.", ephemeral=True)

async def action_accepter_mission(joueur_id, channel):
    guild = channel.guild
    g_id = guild.id
    if g_id in missions_actives and joueur_id in missions_actives[g_id]:
        m_info = missions_actives[g_id][joueur_id]
        profils = charger_profils(g_id)
        initialiser_profil(joueur_id, profils)
        profils[str(joueur_id)]["total_reussies"] += 1
        ajouter_historique(joueur_id, profils, m_info["texte"], "Succès")
        sauvegarder_profils(g_id, profils)
        del missions_actives[g_id][joueur_id]
        
        msg = "✅ **Mission Validée** ! L'objectif est consigné comme réussi dans le grand registre.\n\n🚚 **Un instructeur vas venir récupéré le butin.**"
        await channel.send(msg, view=VueButinRecupere())
        await envoyer_double_notification(guild, msg, f"✅ **Mission accomplie** par <@{joueur_id}> : *\"{m_info['texte']}\"*", joueur_id=joueur_id)
        await envoyer_log_proprietaire(bot, f"LOG ABSOLU - ACTION ACCEPTER MISSION : Joueur {joueur_id} validé sur {guild.name}")
        return True
    return False

async def action_refuser_mission(joueur_id, channel):
    guild = channel.guild
    g_id = guild.id
    if g_id in missions_actives and joueur_id in missions_actives[g_id]:
        m_info = missions_actives[g_id][joueur_id]
        profils = charger_profils(g_id)
        initialiser_profil(joueur_id, profils)
        profils[str(joueur_id)]["total_echouees"] += 1
        ajouter_historique(joueur_id, profils, m_info["texte"], "Échec")
        sauvegarder_profils(g_id, profils)
        del missions_actives[g_id][joueur_id]
        
        msg = f"↩️ **Mission Terminée (Refusé/Échec)**.\n\n{TEXTE_ECHEC}"
        await channel.send(msg, view=VueFermerTicket())
        await envoyer_double_notification(guild, msg, f"❌ **Mission échouée/refusée** pour <@{joueur_id}> : *\"{m_info['texte']}\"*", joueur_id=joueur_id)
        await envoyer_log_proprietaire(bot, f"LOG ABSOLU - ACTION REFUSER MISSION : Joueur {joueur_id} échoué sur {guild.name}")
        return True
    return False

async def action_demander_preuve(joueur_id, channel, guild):
    g_id = guild.id
    if g_id in missions_actives and joueur_id in missions_actives[g_id]:
        m_info = missions_actives[g_id][joueur_id]
        m_info["en_attente"] = True
        
        member = guild.get_member(joueur_id)
        if member:
            await channel.set_permissions(member, read_messages=True, send_messages=True)
            
        role_instructeur = discord.utils.get(guild.roles, name="[ 𝔦𝔫𝔰𝔱𝔯𝔲𝔠𝖙𝔢𝖚🇷 ]")
        mention_ins = role_instructeur.mention if role_instructeur else "@[ 𝔦𝔫𝔰𝔱𝔯𝔲𝔠𝖙𝔢𝖚🇷 ]"
        
        msg_ticket = f"⚠️ <@{joueur_id}>, **{mention_ins} veuillez nous fournir une preuve de l'accomplissement de votre mission.**"
        msg_log_missions = f"📸 {mention_ins} — Une demande de preuve a été envoyée à <@{joueur_id}> dans son ticket {channel.mention}.\nMerci de valider ou refuser ci-dessous une fois la preuve examinée :"
        
        await channel.send(msg_ticket)
        await envoyer_double_notification(guild, msg_ticket, msg_log_missions, view=VueEvaluationMission(joueur_id), joueur_id=joueur_id)
        await envoyer_log_proprietaire(bot, f"LOG ABSOLU - ACTION PREUVE : Demandée pour le joueur {joueur_id} sur {guild.name}")
        return True
    return False

async def gerer_expiration_automatique(guild, channel_id, joueur_id):
    await asyncio.sleep(3600)
    g_id = guild.id
    if g_id not in missions_actives or joueur_id not in missions_actives[g_id]:
        channel = bot.get_channel(channel_id)
        if not channel: return
        
        expiration_time = int((datetime.now() + timedelta(hours=1)).timestamp())
        member = guild.get_member(joueur_id)
        mention_joueur = member.mention if member else f"<@{joueur_id}>"
        
        msg_expiration_auto = (
            f"⚠️ {mention_joueur}, **attention : aucune mission n'a été sélectionnée depuis 1 heure.**\n"
            f"Cet ordre de mission sera définitivement supprimé et annulé **<t:{expiration_time}:R>** (<t:{expiration_time}:t>)."
        )
        try: await channel.send(msg_expiration_auto)
        except: return

        await asyncio.sleep(3600)
        if g_id not in missions_actives or joueur_id not in missions_actives[g_id]:
            channel_final = bot.get_channel(channel_id)
            if channel_final:
                try:
                    await channel_final.delete(reason="Expiration de l'ordre de mission")
                    await envoyer_double_notification(guild, "", f"🗑️ Le ticket d'ordre de {mention_joueur} a été supprimé automatiquement pour inactivité.")
                    await envoyer_log_proprietaire(bot, f"LOG ABSOLU - EXPIRATION AUTO : Ticket de {joueur_id} supprimé pour inactivité sur {guild.name}")
                except Exception as e:
                    await envoyer_log_proprietaire(bot, f"LOG ABSOLU - ERREUR EXPIRATION AUTO : {e}")

@tasks.loop(seconds=1)
async def verifier_temps_missions():
    maintenant = datetime.now()
    
    for guild_id, j_dict in list(missions_actives.items()):
        guild = bot.get_guild(guild_id)
        if not guild: continue
        missions_a_retirer = []

        for joueur_id, m_info in list(j_dict.items()):
            if m_info.get("en_attente", False): continue
            
            channel = bot.get_channel(m_info["channel_id"])
            if not channel: continue
            
            duree_totale = m_info["duree_totale"]
            date_debut = m_info["date_debut"]
            date_fin = m_info["date_fin"]
            temps_restant = date_fin - maintenant
            temps_ecoule = maintenant - date_debut

            if maintenant > date_fin:
                missions_a_retirer.append(joueur_id)
                profils = charger_profils(guild_id)
                initialiser_profil(joueur_id, profils)
                profils[str(joueur_id)]["total_echouees"] += 1
                ajouter_historique(joueur_id, profils, m_info["texte"], "Échec")
                sauvegarder_profils(guild_id, profils)

                role_instructeur = discord.utils.get(guild.roles, name="[ 𝔦𝔫𝔰𝔱𝔯𝔲𝔠𝖙𝔢𝖚🇷 ]")
                mention_ins = role_instructeur.mention if role_instructeur else '@[ 𝔦𝔫𝔰𝔱𝔯𝔲𝔠𝖙𝔢𝖚🇷 ]'
                
                msg_echec = (
                    f"🚨 **MISSION ÉCHOUÉE** 🚨\nLe temps imparti est écoulé ! La mission de <@{joueur_id}> a échoué.\n"
                    f"📢 {mention_ins}, un citoyen a failli à son devoir.\n\n{TEXTE_ECHEC}"
                )
                await channel.send(msg_echec, view=VueFermerTicket())
                await envoyer_double_notification(guild, msg_echec, f"🚨 <@{joueur_id}> a dépassé le temps imparti pour sa mission : *\"{m_info['texte']}\"* !", joueur_id=joueur_id)
                await envoyer_log_proprietaire(bot, f"LOG ABSOLU - TEMPS ECOULE : Mission échouée par dépassement pour {joueur_id} sur {guild.name}")
                
            elif temps_restant <= (duree_totale / 4) and not m_info["alerte_un_quart"]:
                m_info["alerte_un_quart"] = True
                m_info["alerte_moitie"] = True
                jours = temps_restant.days
                heures, reste = divmod(temps_restant.seconds, 3600)
                minutes, secondes = divmod(reste, 60)
                await channel.send(f"⏳ **CRITIQUE** <@{joueur_id}> : -25% du temps restant ! Reste : `{jours}j {heures}h {minutes}mn {secondes}s` !")
                await envoyer_log_proprietaire(bot, f"LOG ABSOLU - ALERTE 25% : Temps critique pour le joueur {joueur_id} sur {guild.name}")
            elif temps_ecoule >= (duree_totale / 2) and not m_info["alerte_moitie"]:
                m_info["alerte_moitie"] = True
                await channel.send(f"🌗 **MI-PARCOURS** <@{joueur_id}> : la moitié du temps s'est écoulée !")

        for joueur_id in missions_a_retirer:
            if joueur_id in missions_actives[guild_id]: 
                del missions_actives[guild_id][joueur_id]

class VueChoixDifficulte(discord.ui.View):
    def __init__(self, joueur_id):
        super().__init__(timeout=600)
        self.joueur_id = joueur_id

    async def attribuer_mission_bouton(self, interaction: discord.Interaction, cat: str):
        if interaction.user.id != self.joueur_id:
            await interaction.response.send_message("❌ Ce ticket ne t'appartient pas.", ephemeral=True)
            return
            
        guild_id = interaction.guild.id
        if guild_id not in missions_actives:
            missions_actives[guild_id] = {}

        if self.joueur_id in missions_actives[guild_id]:
            await interaction.response.send_message("Vous avez déjà une mission active sur ce serveur !", ephemeral=True)
            return

        missions_dispo = charger_missions_fichier(guild_id)
        if not missions_dispo[cat]:
            await interaction.response.send_message(f"❌ Plus de mission disponible dans la catégorie `{cat.upper()}` sur ce serveur.", ephemeral=True)
            return

        mission_choisie = random.choice(missions_dispo[cat])
        duree = extraire_duree(mission_choisie["delai"])
        date_fin = datetime.now() + duree
        timestamp_discord = int(date_fin.timestamp())

        missions_actives[guild_id][self.joueur_id] = {
            "texte": mission_choisie["texte"], "delai_texte": mission_choisie["delai"],
            "date_debut": datetime.now(), "date_fin": date_fin, "duree_totale": duree,
            "cat": cat, "channel_id": interaction.channel.id, "alerte_moitie": False, "alerte_un_quart": False, "en_attente": False
        }

        for child in self.children:
            child.disabled = True

        embed_mission = discord.Embed(title="📜 DECRET ATTRIBUÉ ET CHRONO LANCÉ", color=discord.Color.gold())
        embed_mission.add_field(name="🎯 Objectif", value=f"*{mission_choisie['texte']}*", inline=False)
        embed_mission.add_field(name="⏳ Temps restant réel", value=f"<t:{timestamp_discord}:R> (soit le <t:{timestamp_discord}:f>)", inline=False)
        
        await interaction.response.edit_message(view=self)
        await interaction.channel.send(content=f"{interaction.user.mention}", embed=embed_mission, view=VueGestionJoueurMission(self.joueur_id))
        await envoyer_log_proprietaire(bot, f"LOG ABSOLU - CHOIX DIFFICULTE : Mission {cat} ('{mission_choisie['texte']}') prise par {interaction.user.name} sur {interaction.guild.name}")

    @discord.ui.button(label="🟢 Commune", style=discord.ButtonStyle.secondary, custom_id="btn_commune")
    async def btn_commune(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.attribuer_mission_bouton(interaction, "commune")

    @discord.ui.button(label="🔵 Moyenne", style=discord.ButtonStyle.primary, custom_id="btn_moyenne")
    async def btn_moyenne(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.attribuer_mission_bouton(interaction, "moyenne")

    @discord.ui.button(label="🟠 Difficile", style=discord.ButtonStyle.success, custom_id="btn_difficile")
    async def btn_difficile(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.attribuer_mission_bouton(interaction, "difficile")

    @discord.ui.button(label="🔴 Royal", style=discord.ButtonStyle.danger, custom_id="btn_royal")
    async def btn_royal(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.attribuer_mission_bouton(interaction, "royal")

@bot.command(name="import")
async def importer_missions(ctx, mode: str = "texte"):
    if not verifier_permissions_staff(ctx.author):
        await ctx.send("❌ Permission refusée.")
        return

    guild_id = ctx.guild.id
    if mode.lower() == "tout":
        missions_a_restaurer = [
            ("commune", "récolter 3 stacks de diamants", "3 jours"),
            ("commune", "récolter 3 minerais obscur", "3 jours"),
            ("commune", "récolter 2 fibres de bois millénaires", "3 jours"),
            ("commune", "récolter un dc de blé", "3 jours"),
            ("commune", "récolter 1 dc de buche de bois ( tout type )", "3 jours"),
            ("commune", "faire 15 potions ( force 2, vitesse 1 ou vitesse 2 )", "3 jours"),
            ("commune", "récolter un stack de pomme rouge", "3 jours"),
            ("commune", "craft 3 stockage d'energie", "3 jours"),
            ("commune", "craft 3 stack de steel compressé", "3 jours"),
            ("commune", "récolter 32 minerais d'ashtone ( minerais se trouvant sur le plafond du nether )", "3 jours"),
            
            ("moyenne", "crafter un paneau solaire de tier 1", "7 jours"),
            ("moyenne", "récolter un stack de blocs de diamants", "7 jours"),
            ("moyenne", "recolter un dc de mais", "7 jours"),
            ("moyenne", "récolter 5 fibre de bois millénaires", "7 jours"),
            ("moyenne", "récolter un dc de glowstone", "7 jours"),
            ("moyenne", "récolter 7 minerais obscur", "7 jours"),
            ("moyenne", "récolter un coffre de stack de laine", "7 jours"),
            ("moyenne", "faire un dc de potion de soin jetable", "7 jours"),
            ("moyenne", "récolter 5 stack de blocs d'or", "7 jours"),
            ("moyenne", "faire un dc de potion au choix ( force 2, vitesse 1, vitesse 2 ou invisibilité )", "7 jours"),
            ("moyenne", "récolter 2 tiber", "7 jours"),
            ("moyenne", "craft un écotron", "7 jours"),
            ("moyenne", "produire 32 lingot d'eco", "7 jours"),
            ("moyenne", "récolter 3 zirconiums", "7 jours"),
            ("moyenne", "craft 1 biogenerateur", "7 jours"),
            ("moyenne", "Recruter un joueur", "7 jours"),
            ("moyenne", "craft 10 bouteilles de gaz", "7 jours"),
            ("moyenne", "craft un chargeur élétrique", "7 jours"),
            ("moyenne", "craft 6 stockage d'energie amélioré", "7 jours"),
            ("moyenne", "récolter un dc de tournesol", "7 jours"),
            ("moyenne", "récolté 3 stack d'ashtone ( minerais se trouvant sur le plafond du nether )", "7 jours"),
            
            ("difficile", "crafter un paneau solaire de tier 2", "15 jours"),
            ("difficile", "récolter 15 minerais obscur", "15 jours"),
            ("difficile", "récolter 8 tiber", "15 jours"),
            ("difficile", "craft 3 paneaux solaires T2", "15 jours"),
            ("difficile", "craft une pelle electrique", "15 jours"),
            ("difficile", "produire 7 stack d'éco", "15 jours"),
            ("difficile", "récolter 12 fibre de bois millénaires", "15 jours"),
            ("difficile", "récolter 10 zirconiums", "15 jours"),
            ("difficile", "Craft 3 biogenerateurs", "15 jours"),
            ("difficile", "recruter 3 joueurs", "15 jours"),
            ("difficile", "craft 1 extracteur a gaz", "15 jours"),
            ("difficile", "craft un tracteur", "15 jours"),
            
            ("royal", "craft un pétrolier", "20 jours"),
            ("royal", "craft un serveur", "20 jours"),
            ("royal", "récolter 30 minerais obscur", "20 jours"),
            ("royal", "récolter 30 fibre de bois millénaires", "20 jours"),
            ("royal", "craft 10 paneaux solaires T2", "20 jours"),
            ("royal", "récolter 25 zirconiums", "20 jours")
        ]

        for cat, texte, temps in missions_a_restaurer:
            sauvegarder_mission_fichier(guild_id, cat, texte, temps)
        
        await ctx.send(f"✅ **Succès !** Les {len(missions_a_restaurer)} missions officielles ont toutes été injectées pour ce serveur.")
        return

    if ctx.message.attachments:
        nb_ajoutees = 0
        try:
            attachement = ctx.message.attachments[0]
            contenu_bytes = await attachement.read()
            lignes = contenu_bytes.decode("utf-8").splitlines()
            for ligne in lignes:
                ligne = ligne.strip()
                if not ligne or "|" not in ligne: continue
                parts = ligne.split("|", 2)
                if len(parts) == 3:
                    cat, texte, delai = parts[0].strip(), parts[1].strip(), parts[2].strip()
                    if cat in ["commune", "moyenne", "difficile", "royal"]:
                        sauvegarder_mission_fichier(guild_id, cat, texte, delai)
                        nb_ajoutees += 1
            await ctx.send(f"✅ **Succès !** {nb_ajoutees} missions ont été importées à partir du fichier `.txt` pour ce serveur.")
            return
        except Exception as e:
            await ctx.send(f"❌ Erreur lors de la lecture du fichier joint : {e}")
            return

    await ctx.send("📥 **Envoie ou colle ton bloc de missions** dans les 60 secondes :")
    def check(m): return m.author == ctx.author and m.channel == ctx.channel
    try:
        msg = await bot.wait_for('message', timeout=60.0, check=check)
    except asyncio.TimeoutError:
        await ctx.send("⏰ Temps écoulé. Commande annulée.")
        return

    lignes = msg.content.split('\n')
    nb_ajoutees = 0
    for ligne in lignes:
        ligne_propre = ligne.strip()
        if not ligne_propre or "|" not in ligne_propre: continue
        parts = ligne_propre.split("|", 2)
        if len(parts) == 3:
            cat, texte, delai = parts[0].strip(), parts[1].strip(), parts[2].strip()
            if cat in ["commune", "moyenne", "difficile", "royal"]:
                sauvegarder_mission_fichier(guild_id, cat, texte, delai)
                nb_ajoutees += 1

    await ctx.send(f"✅ **Succès !** {nb_ajoutees} missions ont été importées dynamiquement.")

@bot.command(name="export")
async def exporter_missions(ctx):
    if not verifier_permissions_staff(ctx.author):
        await ctx.send("❌ Permission refusée.")
        return
    file_name = get_file_name(ctx.guild.id)
    if not os.path.exists(file_name):
        await ctx.send("❌ Aucun fichier trouvé.")
        return
    with open(file_name, "r", encoding="utf-8") as f:
        contenu = f.read()
    buffer = io.BytesIO(contenu.encode("utf-8"))
    buffer.seek(0)
    await ctx.send("📤 **Export :**", file=discord.File(buffer, filename=file_name))

@bot.command(name="delall")
async def supprimer_toutes_missions_cmd(ctx):
    if not verifier_permissions_staff(ctx.author):
        await ctx.send("❌ Permission refusée.")
        return
    vider_toutes_missions(ctx.guild.id)
    await ctx.send("🗑️ **Toutes les missions de ce serveur ont été supprimées !**")

@bot.event
async def on_ready():
    if not verifier_temps_missions.is_running(): verifier_temps_missions.start()
    
    # Enregistrement persistant des vues pour éviter l'erreur "Valerius n'a pas répondu à temps" après redémarrage
    bot.add_view(VueBoutonTicket())
    bot.add_view(VueFermerTicket())
    bot.add_view(VueButinRecupere())
    bot.add_view(VueAccueilArrivant())
    bot.add_view(VueGestionJoueurMission())
    bot.add_view(VueEvaluationMission())
    
    salon_accueil = bot.get_channel(WELCOME_CHANNEL_ID)
    if salon_accueil:
        try:
            async for msg in salon_accueil.history(limit=10):
                if msg.author == bot.user and "Bienvenue" in msg.content:
                    break
            else:
                embed_accueil = discord.Embed(
                    title="⚜️ BIENVENUE ⚜️",
                    description="Veuillez sélectionner ci-dessous votre statut ou votre intention en arrivant sur le serveur :",
                    color=discord.Color.gold()
                )
                await salon_accueil.send(content="Bienvenue", embed=embed_accueil, view=VueAccueilArrivant())
        except Exception as e:
            print(f"Erreur envoi panneau d'accueil automatique : {e}")

    try:
        synced = await bot.tree.sync()
        print(f"Bot Valerius Pro — {len(synced)} Commandes Slash synchronisées !")
        await envoyer_log_proprietaire(bot, f"LOG ABSOLU - Bot prêt. {len(synced)} commandes synchronisées avec succès.")
    except Exception as e:
        print(f"Erreur de synchronisation slash: {e}")

@bot.event
async def on_message(message):
    await bot.process_commands(message)
    if message.author.bot: return
    if message.channel.name and "🪖-ordre-" in message.channel.name:
        joueur_id = message.author.id
        g_id = message.guild.id
        if g_id in missions_actives and joueur_id in missions_actives[g_id] and missions_actives[g_id][joueur_id].get("en_attente", False):
            await message.channel.send(f"💬 {message.author.mention}, un instructeur a été ping. Votre demande a bien été envoyée et va être traitée.")
            msg_p = f"📸 **Preuve reçue** pour la mission de <@{joueur_id}>. En attente de l'analyse finale de l'administration :"
            await envoyer_double_notification(message.guild, msg_p, f"📸 Preuve d'accomplissement déposée par <@{joueur_id}> dans {message.channel.mention}.", view=VueEvaluationMission(joueur_id), joueur_id=joueur_id)

async def generer_panneau_aide(interaction: discord.Interaction):
    embed = discord.Embed(title="⚜️ TABLEAU DES ORDRES DE VALERIUS ⚜️", color=discord.Color.gold())
    citoyen_desc = (
        "⚔️ **SYSTÈMÈ DE QUÊTES**\n"
        "`/missionaccomplie` ↳ Déclarer la fin de ta tâche active.\n"
        "`/missions_en_cours` ↳ Statut complet de ton contrat.\n"
        "`/tuto` ↳ Guide complet du citoyen.\n"
        "`/historique` ↳ Consulte ton bilan d'objectifs."
    )
    embed.add_field(name="👥 ESPACE DES CITOYENS", value=citoyen_desc, inline=False)
    if verifier_permissions_staff(interaction.user):
        admin_desc = (
            "🚨 **ADMINISTRATION**\n"
            "`/openticket @joueur` | `/fermerticket` | `/attribuer_mission`\n"
            "`/export_actives` | `/import_actives` | `/total_backup` | `/total_restore`\n"
            "`/missionaccepter` | `/missionrefuser` | `/missionpreuve` | `/listemissions`"
        )
        embed.add_field(name="👑 HAUT COMMANDEMENT", value=admin_desc, inline=False)
    await interaction.response.send_message(embed=embed, view=VueBoutonTicket())

@bot.tree.command(name="aide", description="Affiche le tableau de bord des quêtes de Valerius.")
async def aide(interaction: discord.Interaction): await generer_panneau_aide(interaction)

@bot.tree.command(name="help", description="Affiche le tableau de bord des quêtes de Valerius.")
async def help_cmd(interaction: discord.Interaction): await generer_panneau_aide(interaction)

@bot.tree.command(name="tuto", description="Guide d'utilisation pour mener à bien tes décrets.")
async def tuto(interaction: discord.Interaction):
    embed_tuto = discord.Embed(title="🪖 GUIDE DU CITOYEN DE VALERIUS 🪖", description="Suis ces instructions pour mener à bien tes décrets !", color=discord.Color.green())
    embed_tuto.add_field(name="🎫 Étape 1", value="Ouvre un ticket d'ordre via le panneau d'aide.", inline=False)
    embed_tuto.add_field(name="📜 Étape 2", value="Choisis ta difficulté pour lancer le chrono.", inline=False)
    embed_tuto.add_field(name="🏁 Étape 3", value="Utilise le bouton 'Finir la mission' une fois terminé.", inline=False)
    await interaction.response.send_message(embed=embed_tuto, ephemeral=True)

@bot.tree.command(name="openticket", description="Ouvre un ticket de mission pour un citoyen spécifique (Staff).")
@app_commands.describe(joueur="Le citoyen")
async def openticket(interaction: discord.Interaction, joueur: discord.Member):
    if not verifier_permissions_staff(interaction.user):
        await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        return
    guild = interaction.guild
    g_id = guild.id
    if g_id in missions_actives and joueur.id in missions_actives[g_id]:
        await interaction.response.send_message(f"❌ {joueur.mention} a déjà une mission active !", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    role_instructeur = discord.utils.get(guild.roles, name="[ 𝔦𝔫𝔰𝔱𝔯𝔲𝔠𝖙𝔢𝖚🇷 ]")
    role_palais = discord.utils.get(guild.roles, name="[ Palais Royal ]") or discord.utils.get(guild.roles, name="Palais Royal")

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        joueur: discord.PermissionOverwrite(read_messages=True, send_messages=True, view_channel=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, view_channel=True)
    }
    if role_instructeur: overwrites[role_instructeur] = discord.PermissionOverwrite(read_messages=True, send_messages=True, view_channel=True)
    if role_palais: overwrites[role_palais] = discord.PermissionOverwrite(read_messages=True, send_messages=True, view_channel=True)

    ticket_channel = await guild.create_text_channel(name=f"🪖-ordre-{joueur.name}", overwrites=overwrites, category=interaction.channel.category)
    embed_ticket = discord.Embed(title="⚜️ CENTRE DE SÉLECTION DES DÉCRETS ⚜️", description=f"Ticket ouvert pour {joueur.mention}.", color=discord.Color.dark_red())
    await ticket_channel.send(embed=embed_ticket, view=VueChoixDifficulte(joueur.id))
    asyncio.create_task(gerer_expiration_automatique(guild, ticket_channel.id, joueur.id))
    await interaction.followup.send(f"✅ Ticket créé : {ticket_channel.mention}", ephemeral=True)

@bot.tree.command(name="fermerticket", description="Ferme et supprime le salon actuel (Staff).")
async def fermerticket(interaction: discord.Interaction):
    if not verifier_permissions_staff(interaction.user):
        await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        return
    await interaction.response.send_message("⚙️ Suppression du salon...", ephemeral=True)
    g_id = interaction.guild.id
    if g_id in missions_actives:
        for j_id, m_info in list(missions_actives[g_id].items()):
            if m_info.get("channel_id") == interaction.channel.id:
                del missions_actives[g_id][j_id]
                break
    try: await interaction.channel.delete()
    except: pass

@bot.tree.command(name="attribuer_mission", description="Attribue directement une mission à un joueur (Staff).")
@app_commands.describe(joueur="Le citoyen", categorie="commune, moyenne, difficile, royal")
async def attribuer_mission(interaction: discord.Interaction, joueur: discord.Member, categorie: str):
    if not verifier_permissions_staff(interaction.user):
        await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        return
    cat = categorie.lower().strip()
    guild_id = interaction.guild.id
    if guild_id not in missions_actives: missions_actives[guild_id] = {}
    if joueur.id in missions_actives[guild_id]:
        await interaction.response.send_message("❌ Ce joueur a déjà une mission active.", ephemeral=True)
        return
    missions_dispo = charger_missions_fichier(guild_id)
    if not missions_dispo.get(cat):
        await interaction.response.send_message("❌ Catégorie vide.", ephemeral=True)
        return
    mission_choisie = random.choice(missions_dispo[cat])
    duree = extraire_duree(mission_choisie["delai"])
    date_fin = datetime.now() + duree
    timestamp_discord = int(date_fin.timestamp())

    missions_actives[guild_id][joueur.id] = {
        "texte": mission_choisie["texte"], "delai_texte": mission_choisie["delai"],
        "date_debut": datetime.now(), "date_fin": date_fin, "duree_totale": duree,
        "cat": cat, "channel_id": interaction.channel.id, "alerte_moitie": False, "alerte_un_quart": False, "en_attente": False
    }
    embed = discord.Embed(title="📜 DÉCRET IMPÉRIAL ATTRIBUÉ", color=discord.Color.gold())
    embed.add_field(name="🎯 Objectif", value=f"*{mission_choisie['texte']}*", inline=False)
    embed.add_field(name="⏳ Fin", value=f"<t:{timestamp_discord}:R>", inline=False)
    await interaction.response.send_message(content=f"✅ Attribué à {joueur.mention} !", embed=embed, view=VueGestionJoueurMission(joueur.id))

@bot.tree.command(name="export_actives", description="Exporte les missions en cours (.txt).")
async def export_actives(interaction: discord.Interaction):
    if not verifier_permissions_staff(interaction.user):
        await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        return
    guild_id = interaction.guild.id
    actives_serveur = {}
    if guild_id in missions_actives:
        for j_id, m_data in missions_actives[guild_id].items():
            actives_serveur[str(j_id)] = {
                "texte": m_data["texte"], "delai_texte": m_data["delai_texte"],
                "date_debut": m_data["date_debut"].isoformat(), "date_fin": m_data["date_fin"].isoformat(),
                "duree_totale_seconds": m_data["duree_totale"].total_seconds(), "cat": m_data["cat"],
                "channel_id": m_data["channel_id"], "alerte_moitie": m_data["alerte_moitie"],
                "alerte_un_quart": m_data["alerte_un_quart"], "en_attente": m_data["en_attente"]
            }
    if not actives_serveur:
        await interaction.response.send_message("⚠️ Aucune mission active.", ephemeral=True)
        return
    buffer = io.BytesIO(json.dumps(actives_serveur, indent=4, ensure_ascii=False).encode("utf-8"))
    buffer.seek(0)
    await interaction.response.send_message("📤 **Missions en cours :**", file=discord.File(buffer, filename=f"actives_{guild_id}.txt"), ephemeral=True)

@bot.tree.command(name="import_actives", description="Importe les missions en cours (.txt).")
async def import_actives(interaction: discord.Interaction, fichier: discord.Attachment):
    if not verifier_permissions_staff(interaction.user):
        await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    guild_id = interaction.guild.id
    if guild_id not in missions_actives: missions_actives[guild_id] = {}
    try:
        donnees = json.loads((await fichier.read()).decode("utf-8"))
        for str_j_id, m_data in donnees.items():
            if str_j_id.isdigit():
                missions_actives[guild_id][int(str_j_id)] = {
                    "texte": m_data["texte"], "delai_texte": m_data["delai_texte"],
                    "date_debut": datetime.fromisoformat(m_data["date_debut"]),
                    "date_fin": datetime.fromisoformat(m_data["date_fin"]),
                    "duree_totale": timedelta(seconds=m_data["duree_totale_seconds"]),
                    "cat": m_data["cat"], "channel_id": m_data["channel_id"],
                    "alerte_moitie": m_data["alerte_moitie"], "alerte_un_quart": m_data["alerte_un_quart"],
                    "en_attente": m_data["en_attente"]
                }
        await interaction.followup.send("✅ Missions en cours restaurées !", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Erreur : {e}", ephemeral=True)

@bot.tree.command(name="total_backup", description="Sauvegarde complète du bot (.json).")
async def total_backup(interaction: discord.Interaction):
    if not verifier_permissions_staff(interaction.user):
        await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    donnees_globales = {"missions_actives": {}, "fichiers_disques": {}}
    for g_id, j_dict in missions_actives.items():
        donnees_globales["missions_actives"][str(g_id)] = {}
        for j_id, m_data in j_dict.items():
            donnees_globales["missions_actives"][str(g_id)][str(j_id)] = {
                "texte": m_data["texte"], "delai_texte": m_data["delai_texte"],
                "date_debut": m_data["date_debut"].isoformat(), "date_fin": m_data["date_fin"].isoformat(),
                "duree_totale_seconds": m_data["duree_totale"].total_seconds(), "cat": m_data["cat"],
                "channel_id": m_data["channel_id"], "alerte_moitie": m_data["alerte_moitie"],
                "alerte_un_quart": m_data["alerte_un_quart"], "en_attente": m_data["en_attente"]
            }
    import glob
    for f_path in glob.glob("valerius_missions_*.txt") + glob.glob("valerius_profils_*.json"):
        if os.path.exists(f_path):
            with open(f_path, "r", encoding="utf-8") as f: donnees_globales["fichiers_disques"][f_path] = f.read()

    buffer = io.BytesIO(json.dumps(donnees_globales, indent=4, ensure_ascii=False).encode("utf-8"))
    buffer.seek(0)
    await interaction.followup.send("📦 **Sauvegarde complète :**", file=discord.File(buffer, filename=f"backup_{datetime.now().strftime('%Y%m%d_%H%M')}.json"), ephemeral=True)

@bot.tree.command(name="total_restore", description="Restauration complète à partir d'un .json.")
async def total_restore(interaction: discord.Interaction, fichier: discord.Attachment):
    if not verifier_permissions_staff(interaction.user):
        await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    try:
        donnees = json.loads((await fichier.read()).decode("utf-8"))
        for f_path, f_contenu in donnees.get("fichiers_disques", {}).items():
            with open(f_path, "w", encoding="utf-8") as f: f.write(f_contenu)
        
        global missions_actives
        missions_actives.clear()
        for str_g_id, j_dict in donnees.get("missions_actives", {}).items():
            g_id = int(str_g_id)
            missions_actives[g_id] = {}
            guild_obj = bot.get_guild(g_id)
            for str_j_id, m_data in j_dict.items():
                old_chan = m_data["channel_id"]
                target_chan = bot.get_channel(old_chan)
                if not target_chan and guild_obj: target_chan = interaction.channel
                missions_actives[g_id][int(str_j_id)] = {
                    "texte": m_data["texte"], "delai_texte": m_data["delai_texte"],
                    "date_debut": datetime.fromisoformat(m_data["date_debut"]),
                    "date_fin": datetime.fromisoformat(m_data["date_fin"]),
                    "duree_totale": timedelta(seconds=m_data["duree_totale_seconds"]),
                    "cat": m_data["cat"], "channel_id": target_chan.id if target_chan else old_chan,
                    "alerte_moitie": m_data["alerte_moitie"], "alerte_un_quart": m_data["alerte_un_quart"],
                    "en_attente": m_data["en_attente"]
                }
        await interaction.followup.send("✅ Restauration totale effectuée avec succès !", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Erreur : {e}", ephemeral=True)

@bot.tree.command(name="missions_en_cours", description="Affiche le statut de ta mission active.")
async def missions_en_cours(interaction: discord.Interaction):
    g_id = interaction.guild.id
    if g_id not in missions_actives or interaction.user.id not in missions_actives[g_id]:
        await interaction.response.send_message("⚪ Tu n'as aucune mission active actuellement.", ephemeral=True)
        return
    m = missions_actives[g_id][interaction.user.id]
    ts = int(m["date_fin"].timestamp())
    if m.get("en_attente", False):
        await interaction.response.send_message(f"👤 <@{interaction.user.id}> [**{m['cat'].upper()}**] -> *\"{m['texte']}\"* 🛑 **GELÉ (En attente d'évaluation)**", ephemeral=True)
    else:
        await interaction.response.send_message(f"👤 <@{interaction.user.id}> [**{m['cat'].upper()}**] -> *\"{m['texte']}\"* Fin : <t:{ts}:R>", ephemeral=True)

@bot.tree.command(name="missionaccomplie", description="Déclare l'objectif en cours comme accompli.")
async def missionaccomplie(interaction: discord.Interaction):
    joueur = interaction.user
    g_id = interaction.guild.id
    role_instructeur = discord.utils.get(interaction.guild.roles, name="[ 𝔦𝔫𝔰𝔱𝔯𝔲𝔠𝖙𝔢𝖚🇷 ]")
    mention_ins = role_instructeur.mention if role_instructeur else '@[ 𝔦𝔫𝔰𝔱𝔯𝔲𝔠𝖙𝔢𝖚🇷 ]'
    
    if g_id in missions_actives and joueur.id in missions_actives[g_id]:
        m_info = missions_actives[g_id][joueur.id]
        if not m_info.get("en_attente", False):
            m_info["en_attente"] = True
            m_info["moment_gel"] = datetime.now()
            
        await interaction.channel.set_permissions(joueur, read_messages=True, send_messages=False)
        await interaction.response.send_message(f"💬 {joueur.mention}, votre demande a été envoyée aux instructeurs. Votre chrono est gelé.")
        
        msg_comp = (
            f"📢 {mention_ins} ! {joueur.mention} déclare avoir fini sa mission : *\"{m_info['texte']}\"* !\n"
            f"⏱️ **Le chrono est mis en pause.** Choisissez l'action appropriée :"
        )
        await envoyer_double_notification(interaction.guild, msg_comp, f"📢 {mention_ins} — <@{joueur.id}> a fini sa mission : *\"{m_info['texte']}\"* dans {interaction.channel.mention}", view=VueEvaluationMission(joueur.id), joueur_id=joueur.id)
        return
    await interaction.response.send_message("❌ Tu n'as aucune mission active en cours sur ce serveur.", ephemeral=True)

@bot.tree.command(name="historique", description="Affiche l'historique des décrets.")
@app_commands.describe(joueur="Le joueur")
async def historique(interaction: discord.Interaction, joueur: discord.Member = None):
    cible = joueur or interaction.user
    profils = charger_profils(interaction.guild.id)
    initialiser_profil(cible.id, profils)
    userData = profils[str(cible.id)]
    embed = discord.Embed(title=f"📜 ARCHIVES — {cible.display_name}", color=discord.Color.blue())
    embed.add_field(name="📊 Bilan", value=f"🟢 Réussites : `{userData['total_reussies']}`\n🔴 Échouées : `{userData['total_echouees']}`", inline=False)
    hist = userData["historique"]
    if not hist:
        embed.add_field(name="📜 Historique", value="*Aucune mission enregistrée.*", inline=False)
    else:
        corps = "\n".join([("✅" if i["statut"] == "Succès" else "❌") + f" **[{i['date']}]** — {i['texte']}" for i in hist[:10]])
        embed.add_field(name="📜 Historique", value=corps, inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="missionaccepter", description="Valide manuellement la mission d'un joueur (Staff).")
@app_commands.describe(joueur="Le citoyen")
async def missionaccepter(interaction: discord.Interaction, joueur: discord.Member):
    if not verifier_permissions_staff(interaction.user):
        await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        return
    await interaction.response.defer()
    if await action_accepter_mission(joueur.id, interaction.channel):
        await interaction.followup.send(f"✅ Mission de {joueur.mention} acceptée.")
    else:
        await interaction.followup.send("❌ Ce joueur n'a pas de mission active.")

@bot.tree.command(name="missionrefuser", description="Refuse manuellement la mission d'un joueur (Staff).")
@app_commands.describe(joueur="Le citoyen")
async def missionrefuser(interaction: discord.Interaction, joueur: discord.Member):
    if not verifier_permissions_staff(interaction.user):
        await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        return
    await interaction.response.defer()
    if await action_refuser_mission(joueur.id, interaction.channel):
        await interaction.followup.send(f"❌ Mission de {joueur.mention} refusée.")
    else:
        await interaction.followup.send("❌ Ce joueur n'a pas de mission active.")

@bot.tree.command(name="missionpreuve", description="Exige une preuve au joueur (Staff).")
@app_commands.describe(joueur="Le citoyen")
async def missionpreuve(interaction: discord.Interaction, joueur: discord.Member):
    if not verifier_permissions_staff(interaction.user):
        await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        return
    await interaction.response.defer()
    if await action_demander_preuve(joueur.id, interaction.channel, interaction.guild):
        await interaction.followup.send(f"📸 Demande de preuve transmise à {joueur.mention}.")
    else:
        await interaction.followup.send("❌ Ce joueur n'a pas de mission active.")

@bot.tree.command(name="listemissions", description="Liste les missions (Staff).")
async def listemissions(interaction: discord.Interaction):
    if not verifier_permissions_staff(interaction.user):
        await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        return
    missions_dispo = charger_missions_fichier(interaction.guild.id)
    texte = "⚜️ **CATALOGUE DES MISSIONS** ⚜️\n"
    for cat in ["commune", "moyenne", "difficile", "royal"]:
        texte += f"\n__**{cat.upper()}**__\n"
        for i, m in enumerate(missions_dispo[cat], 1):
            texte += f"**{i}.** {m['texte']} ({m['delai']})\n"
    if len(texte) > 1900: texte = texte[:1900] + "\n..."
    await interaction.response.send_message(texte, ephemeral=True)

@bot.tree.command(name="addmission", description="Ajoute une mission (Staff).")
@app_commands.describe(categorie="commune, moyenne, difficile, royal", texte="Objectif", temps="ex: 3 jours")
async def addmission(interaction: discord.Interaction, categorie: str, texte: str, temps: str):
    if not verifier_permissions_staff(interaction.user):
        await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        return
    cat = categorie.lower().strip()
    if cat not in ["commune", "moyenne", "difficile", "royal"]:
        await interaction.response.send_message("❌ Catégorie invalide.", ephemeral=True)
        return
    sauvegarder_mission_fichier(interaction.guild.id, cat, texte, temps)
    await interaction.response.send_message(f"✅ Mission ajoutée dans `{cat}` : *{texte}* ({temps})", ephemeral=True)

keep_alive()
token = os.environ.get("DISCORD_TOKEN")
if token: bot.run(token)
else: print("Erreur : Aucun token Discord trouvé.")
