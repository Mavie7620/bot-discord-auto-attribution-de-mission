import discord
from discord import app_commands
from discord.ext import tasks, commands
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

PROPRIETAIRE_ID = 1109866808321769472
WELCOME_CHANNEL_ID = 1534604841660190792
ATTENTE_MOOV_ID = 1534604587992875280
SALON_PALAIS_ROYAL_ID = 1519322938430722129
SALON_VALIDATION_MISSION_ID = 1534638388286853273

CONFIG_FILE = "valerius_config.json"

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {"verification_code": "CODE1234", "enabled": True}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"verification_code": "CODE1234", "enabled": True}

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

def get_file_name(guild_id):
    return f"valerius_missions_{guild_id}.txt"

def get_profiles_file(guild_id):
    return f"valerius_profils_{guild_id}.json"

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

def ajouter_historique(p_id, profils, texte, statut, cat="inconnu"):
    s_id = str(p_id)
    initialiser_profil(p_id, profils)
    profils[s_id]["historique"].insert(0, {
        "texte": texte,
        "statut": statut,
        "categorie": cat,
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
    if user.id == PROPRIETAIRE_ID:
        return True
    if not hasattr(user, "roles") or not hasattr(user, "guild_permissions"):
        return False
    roles_noms = [r.name for r in user.roles]
    return user.guild_permissions.administrator or "[ 𝔦𝔫𝔰𝔱𝔯𝔲𝔠𝖙𝔢𝖚🇷 ]" in roles_noms or "[ Palais Royal ]" in roles_noms or "Palais Royal" in roles_noms or any(r.permissions.manage_channels or r.permissions.administrator for r in user.roles)

def verifier_acces_verifie(interaction: discord.Interaction):
    config = load_config()
    if not config["enabled"]:
        return True
    if interaction.user.id == PROPRIETAIRE_ID or verifier_permissions_staff(interaction.user):
        return True
    if not interaction.guild:
        return False
    role_verifie = discord.utils.get(interaction.guild.roles, name="Vérifié")
    if role_verifie and role_verifie in interaction.user.roles:
        return True
    return False

async def envoyer_log_proprietaire(bot_instance, texte_log, view=None, guild_target=None, joueur_id_target=None):
    membre = bot_instance.get_user(PROPRIETAIRE_ID)
    if not membre:
        try: membre = await bot_instance.fetch_user(PROPRIETAIRE_ID)
        except Exception: pass
            
    if membre:
        try:
            v = view(guild_target, joueur_id_target) if (view and guild_target and joueur_id_target) else view
            await membre.send(f"📋 **[LOG GLOBAL ABSOLU - VALERIUS]** : {texte_log}", view=v)
            return
        except Exception: pass

async def envoyer_double_notification(guild, msg_ticket, msg_missions, view=None, joueur_id=None):
    salon_missions = guild.get_channel(SALON_VALIDATION_MISSION_ID) or discord.utils.get(guild.text_channels, name="validation-mission")
    if salon_missions:
        try: 
            v_obj = view(joueur_id) if (view and joueur_id and callable(view)) else view
            await salon_missions.send(msg_missions, view=v_obj)
        except Exception: pass
    await envoyer_log_proprietaire(guild._state._get_client(), f"[{guild.name}] {msg_missions}", view=VueEvaluationMissionMP if view else None, guild_target=guild, joueur_id_target=joueur_id)

class VueFermerTicket(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="🔒 Fermer le ticket", style=discord.ButtonStyle.danger, custom_id="btn_fermer_ticket")
    async def fermer_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⚙️ Suppression du salon en cours...", ephemeral=True)
        g_id = interaction.guild.id
        if g_id in missions_actives:
            for j_id, m_info in list(missions_actives[g_id].items()):
                if m_info.get("channel_id") == interaction.channel.id or f"🪖-ordre-" in interaction.channel.name:
                    del missions_actives[g_id][j_id]
                    break
        try: await interaction.channel.delete()
        except: pass

class VueButinRecupere(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="📦 Butin récupéré", style=discord.ButtonStyle.primary, custom_id="btn_butin_recupere")
    async def butin_recupere(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children: child.disabled = True
        try: await interaction.response.edit_message(view=self)
        except: pass
        await interaction.channel.send("✅ **Le butin a été récupéré avec succès par l'instructeur.**", view=VueFermerTicket())

class VueAccueilArrivant(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="👑 Je suis greyjoy", style=discord.ButtonStyle.danger, custom_id="btn_greyjoy")
    async def greyjoy_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        role_palais = discord.utils.get(interaction.guild.roles, name="[ Palais Royal ]") or discord.utils.get(interaction.guild.roles, name="Palais Royal")
        salon_cible = interaction.guild.get_channel(SALON_PALAIS_ROYAL_ID)
        mention_role = role_palais.mention if role_palais else "@[ Palais Royal ]"
        if salon_cible:
            try:
                await salon_cible.send(f"🚨 {mention_role} ! Le membre {interaction.user.mention} ({interaction.user.name}) s'identifie en tant que Greyjoy.")
                await interaction.response.send_message(f"✅ Un haut gradé a été prévenu dans le salon {salon_cible.mention} !", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ Erreur : {e}", ephemeral=True)
        else:
            await interaction.response.send_message(f"🚨 Un haut gradé a été ping : {mention_role} ! Le membre {interaction.user.mention} s'identifie en tant que Greyjoy.", ephemeral=True)

    @discord.ui.button(label="👤 Je suis un visiteurs", style=discord.ButtonStyle.secondary, custom_id="btn_visiteur")
    async def visiteur_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        role_etranger = discord.utils.get(interaction.guild.roles, name="[💥] Etranger [💥]") or discord.utils.get(interaction.guild.roles, name="etranger")
        if role_etranger:
            try:
                await interaction.user.add_roles(role_etranger)
                await interaction.response.send_message(f"✅ Rôle **{role_etranger.name}** attribué !", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ Erreur : {e}", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Le rôle `[💥] Etranger [💥]` est introuvable.", ephemeral=True)

    @discord.ui.button(label="⚔️ Je souhaite etre recruter", style=discord.ButtonStyle.success, custom_id="btn_recrutement")
    async def recrutement_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        role_recrutement = discord.utils.get(interaction.guild.roles, name="en cours de recrutement")
        salon_attente = interaction.guild.get_channel(ATTENTE_MOOV_ID) or discord.utils.get(interaction.guild.text_channels, name="attente-moov")
        if not role_recrutement:
            await interaction.response.send_message("❌ Le rôle `en cours de recrutement` est introuvable.", ephemeral=True)
            return
        try:
            await interaction.user.add_roles(role_recrutement)
            if salon_attente:
                await salon_attente.set_permissions(interaction.user, read_messages=True, send_messages=True, connect=True)
                await interaction.response.send_message(f"✅ Rôle attribué et accès au salon {salon_attente.mention} accordé !", ephemeral=True)
            else:
                await interaction.response.send_message("✅ Rôle attribué.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Erreur : {e}", ephemeral=True)

class VueGestionJoueurMission(discord.ui.View):
    def __init__(self, joueur_id=None):
        super().__init__(timeout=None)
        self.joueur_id = joueur_id

    @discord.ui.button(label="🏁 Finir la mission", style=discord.ButtonStyle.success, custom_id="joueur_finir_mission")
    async def joueur_finir(self, interaction: discord.Interaction, button: discord.ui.Button):
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
            await interaction.response.send_message("❌ Aucune mission active sur ce serveur.", ephemeral=True)
            return
        m_info = missions_actives[g_id][target_id]
        if not m_info.get("en_attente", False):
            m_info["en_attente"] = True
            m_info["moment_gel"] = datetime.now()
        for child in self.children: child.disabled = True
        try: await interaction.response.edit_message(view=self)
        except: 
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)

        role_instructeur = discord.utils.get(interaction.guild.roles, name="[ 𝔦𝔫𝔰𝔱𝔯𝔲𝔠𝖙𝔢𝖚🇷 ]")
        mention_ins = role_instructeur.mention if role_instructeur else '@[ 𝔦𝔫𝔰𝔱𝔯𝔲𝔠𝖙𝔢𝖚🇷 ]'
        member_obj = interaction.guild.get_member(target_id)
        if member_obj: await interaction.channel.set_permissions(member_obj, read_messages=True, send_messages=False)
        await interaction.channel.send(f"💬 <@{target_id}>, un instructeur a été notifié.")
        msg_fin = f"📢 {mention_ins} ! <@{target_id}> déclare avoir fini sa mission : *\"{m_info['texte']}\"* !"
        await envoyer_double_notification(interaction.guild, msg_fin, f"📢 {mention_ins} — <@{target_id}> demande validation pour : *\"{m_info['texte']}\"*", view=VueEvaluationMission, joueur_id=target_id)

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
            await interaction.response.send_message("❌ Tu ne peux pas abandonner la mission d'autrui.", ephemeral=True)
            return
        if g_id not in missions_actives or target_id not in missions_actives[g_id]:
            await interaction.response.send_message("❌ Pas de mission active à abandonner.", ephemeral=True)
            return
        for child in self.children: child.disabled = True
        try: await interaction.response.edit_message(view=self)
        except:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
        await action_refuser_mission(target_id, interaction.channel)

class VueEvaluationMission(discord.ui.View):
    def __init__(self, joueur_id=None):
        super().__init__(timeout=None)
        self.joueur_id = joueur_id

    @discord.ui.button(label="✅ Accepter", style=discord.ButtonStyle.success, custom_id="eval_accepter")
    async def eval_accepter(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not verifier_permissions_staff(interaction.user):
            await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
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
            if not interaction.response.is_done():
                await interaction.response.send_message("✅ Mission acceptée.", ephemeral=True)
        else: 
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Joueur introuvable.", ephemeral=True)

    @discord.ui.button(label="❌ Refuser", style=discord.ButtonStyle.danger, custom_id="eval_refuser")
    async def eval_refuser(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not verifier_permissions_staff(interaction.user):
            await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
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
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Mission refusée.", ephemeral=True)
        else: 
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Joueur introuvable.", ephemeral=True)

    @discord.ui.button(label="📸 Demander des preuves", style=discord.ButtonStyle.primary, custom_id="eval_preuve")
    async def eval_preuve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not verifier_permissions_staff(interaction.user):
            await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
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
            if not interaction.response.is_done():
                await interaction.response.send_message("📸 Preuve demandée.", ephemeral=True)
        else: 
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Joueur introuvable.", ephemeral=True)

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
            chan_cible = self.guild_target.get_channel(SALON_VALIDATION_MISSION_ID) or discord.utils.get(self.guild_target.text_channels, name="validation-mission")
        if chan_cible:
            await action_accepter_mission(self.joueur_id, chan_cible)
            await interaction.followup.send("✅ Mission acceptée.", ephemeral=True)
        else: await interaction.followup.send("❌ Salon introuvable.", ephemeral=True)

    @discord.ui.button(label="❌ Refuser (MP)", style=discord.ButtonStyle.danger, custom_id="eval_mp_refuser")
    async def eval_mp_refuser(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children: child.disabled = True
        try: await interaction.response.edit_message(view=self)
        except: pass
        chan_cible = None
        if self.guild_target and self.guild_target.id in missions_actives and self.joueur_id in missions_actives[self.guild_target.id]:
            chan_cible = bot.get_channel(missions_actives[self.guild_target.id][self.joueur_id]["channel_id"])
        if not chan_cible and self.guild_target:
            chan_cible = self.guild_target.get_channel(SALON_VALIDATION_MISSION_ID) or discord.utils.get(self.guild_target.text_channels, name="validation-mission")
        if chan_cible:
            await action_refuser_mission(self.joueur_id, chan_cible)
            await interaction.followup.send("❌ Mission refusée.", ephemeral=True)
        else: await interaction.followup.send("❌ Salon introuvable.", ephemeral=True)

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
            await interaction.followup.send("📸 Preuve demandée.", ephemeral=True)
        else: await interaction.followup.send("❌ Salon introuvable.", ephemeral=True)

async def action_accepter_mission(joueur_id, channel):
    guild = channel.guild
    g_id = guild.id
    if g_id in missions_actives and joueur_id in missions_actives[g_id]:
        m_info = missions_actives[g_id][joueur_id]
        profils = charger_profils(g_id)
        initialiser_profil(joueur_id, profils)
        profils[str(joueur_id)]["total_reussies"] += 1
        ajouter_historique(joueur_id, profils, m_info["texte"], "Succès", m_info["cat"])
        sauvegarder_profils(g_id, profils)
        del missions_actives[g_id][joueur_id]
        msg = "✅ **Mission Validée** !\n\n🚚 **Un instructeur va venir récupérer le butin.**"
        await channel.send(msg, view=VueButinRecupere())
        await envoyer_double_notification(guild, msg, f"✅ **Mission accomplie** par <@{joueur_id}> : *\"{m_info['texte']}\"*", joueur_id=joueur_id)
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
        ajouter_historique(joueur_id, profils, m_info["texte"], "Échec", m_info["cat"])
        sauvegarder_profils(g_id, profils)
        del missions_actives[g_id][joueur_id]
        msg = f"↩️ **Mission Terminée (Refusé/Échec)**.\n\n{TEXTE_ECHEC}"
        await channel.send(msg, view=VueFermerTicket())
        await envoyer_double_notification(guild, msg, f"❌ **Mission échouée/refusée** pour <@{joueur_id}> : *\"{m_info['texte']}\"*", joueur_id=joueur_id)
        return True
    return False

async def action_demander_preuve(joueur_id, channel, guild):
    g_id = guild.id
    if g_id in missions_actives and joueur_id in missions_actives[g_id]:
        m_info = missions_actives[g_id][joueur_id]
        m_info["en_attente"] = True
        member = guild.get_member(joueur_id)
        if member: await channel.set_permissions(member, read_messages=True, send_messages=True)
        role_instructeur = discord.utils.get(guild.roles, name="[ 𝔦𝔫𝔰𝔱𝔯𝔲𝔠𝖙𝔢𝖚🇷 ]")
        mention_ins = role_instructeur.mention if role_instructeur else "@[ 𝔦𝔫𝔰𝔱𝔯𝔲𝔠𝖙𝔢𝖚🇷 ]"
        msg_ticket = f"⚠️ <@{joueur_id}>, **{mention_ins} veuillez fournir une image ou photo comme preuve.**"
        msg_log_missions = f"📸 {mention_ins} — Demande de preuve envoyée à <@{joueur_id}> dans {channel.mention}."
        await channel.send(msg_ticket)
        await envoyer_double_notification(guild, msg_ticket, msg_log_missions, view=VueEvaluationMission(joueur_id), joueur_id=joueur_id)
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
        msg_expiration_auto = f"⚠️ {mention_joueur}, aucune mission sélectionnée depuis 1 heure. Suppression dans **<t:{expiration_time}:R>**."
        try: await channel.send(msg_expiration_auto)
        except: return
        await asyncio.sleep(3600)
        if g_id not in missions_actives or joueur_id not in missions_actives[g_id]:
            channel_final = bot.get_channel(channel_id)
            if channel_final:
                try:
                    await channel_final.delete(reason="Expiration de l'ordre")
                    await envoyer_double_notification(guild, "", f"🗑️ Le ticket de {mention_joueur} a été supprimé pour inactivité.")
                except: pass

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
            date_fin = m_info["date_fin"]
            temps_restant = date_fin - maintenant
            temps_ecoule = maintenant - m_info["date_debut"]

            if maintenant > date_fin:
                missions_a_retirer.append(joueur_id)
                profils = charger_profils(guild_id)
                initialiser_profil(joueur_id, profils)
                profils[str(joueur_id)]["total_echouees"] += 1
                ajouter_historique(joueur_id, profils, m_info["texte"], "Échec", m_info["cat"])
                sauvegarder_profils(guild_id, profils)
                role_instructeur = discord.utils.get(guild.roles, name="[ 𝔦𝔫𝔰𝔱𝔯𝔲𝔠𝖙𝔢𝖚🇷 ]")
                mention_ins = role_instructeur.mention if role_instructeur else '@[ 𝔦𝔫𝔰𝔱𝔯𝔲𝔠𝖙𝔢𝖚🇷 ]'
                msg_echec = f"🚨 **MISSION ÉCHOUÉE** 🚨\nTemps écoulé pour <@{joueur_id}> !\n\n{TEXTE_ECHEC}"
                await channel.send(msg_echec, view=VueFermerTicket())
                await envoyer_double_notification(guild, msg_echec, f"🚨 <@{joueur_id}> a dépassé le temps imparti.", joueur_id=joueur_id)
            elif temps_restant <= (duree_totale / 4) and not m_info["alerte_un_quart"]:
                m_info["alerte_un_quart"] = True
                m_info["alerte_moitie"] = True
                jours = temps_restant.days
                heures, reste = divmod(temps_restant.seconds, 3600)
                minutes, secondes = divmod(reste, 60)
                await channel.send(f"⏳ **CRITIQUE** <@{joueur_id}> : Reste `{jours}j {heures}h {minutes}mn {secondes}s` !")
            elif temps_ecoule >= (duree_totale / 2) and not m_info["alerte_moitie"]:
                m_info["alerte_moitie"] = True
                await channel.send(f"🌗 **MI-PARCOURS** <@{joueur_id}> !")

        for joueur_id in missions_a_retirer:
            if joueur_id in missions_actives[guild_id]: del missions_actives[guild_id][joueur_id]

class VueBoutonTicket(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="🎫 Ouvrir un Ticket de Mission", style=discord.ButtonStyle.green, custom_id="btn_ouvrir_ticket")
    async def ouvrir_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        joueur = interaction.user
        g_id = guild.id
        if g_id in missions_actives and joueur.id in missions_actives[g_id]:
            await interaction.response.send_message("Vous avez déjà une mission active !", ephemeral=True)
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
        ticket_channel = await guild.create_text_channel(name=f"🪖-ordre-{joueur.name}", overwrites=overwrites, category=interaction.channel.category if interaction.channel.category else None)
        embed_ticket = discord.Embed(title="⚜️ CENTRE DE SÉLECTION DES DÉCRETS ⚜️", description=f"Bienvenue {joueur.mention}. Choisis la difficulté :", color=discord.Color.dark_red())
        await ticket_channel.send(embed=embed_ticket, view=VueChoixDifficulte(joueur.id))
        asyncio.create_task(gerer_expiration_automatique(guild, ticket_channel.id, joueur.id))
        await interaction.followup.send(f"✅ Ton ticket : {ticket_channel.mention}", ephemeral=True)

class VueChoixDifficulte(discord.ui.View):
    def __init__(self, joueur_id):
        super().__init__(timeout=600)
        self.joueur_id = joueur_id

    async def attribuer_mission_bouton(self, interaction: discord.Interaction, cat: str):
        if interaction.user.id != self.joueur_id:
            await interaction.response.send_message("❌ Ce ticket ne t'appartient pas.", ephemeral=True)
            return
        guild_id = interaction.guild.id
        if guild_id not in missions_actives: missions_actives[guild_id] = {}
        if self.joueur_id in missions_actives[guild_id]:
            await interaction.response.send_message("Mission active déjà existante !", ephemeral=True)
            return
        missions_dispo = charger_missions_fichier(guild_id)
        if not missions_dispo[cat]:
            await interaction.response.send_message(f"❌ Plus de mission dans `{cat.upper()}`.", ephemeral=True)
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
        for child in self.children: child.disabled = True
        embed_mission = discord.Embed(title="📜 DECRET ATTRIBUÉ ET CHRONO LANCÉ", color=discord.Color.gold())
        embed_mission.add_field(name="🎯 Objectif", value=f"*{mission_choisie['texte']}*", inline=False)
        embed_mission.add_field(name="⏳ Temps restant", value=f"<t:{timestamp_discord}:R>", inline=False)
        await interaction.response.edit_message(view=self)
        await interaction.channel.send(content=f"{interaction.user.mention}", embed=embed_mission, view=VueGestionJoueurMission(self.joueur_id))

    @discord.ui.button(label="🟢 Commune", style=discord.ButtonStyle.secondary, custom_id="btn_commune")
    async def btn_commune(self, interaction: discord.Interaction, button: discord.ui.Button): await self.attribuer_mission_bouton(interaction, "commune")
    @discord.ui.button(label="🔵 Moyenne", style=discord.ButtonStyle.primary, custom_id="btn_moyenne")
    async def btn_moyenne(self, interaction: discord.Interaction, button: discord.ui.Button): await self.attribuer_mission_bouton(interaction, "moyenne")
    @discord.ui.button(label="🟠 Difficile", style=discord.ButtonStyle.success, custom_id="btn_difficile")
    async def btn_difficile(self, interaction: discord.Interaction, button: discord.ui.Button): await self.attribuer_mission_bouton(interaction, "difficile")
    @discord.ui.button(label="🔴 Royal", style=discord.ButtonStyle.danger, custom_id="btn_royal")
    async def btn_royal(self, interaction: discord.Interaction, button: discord.ui.Button): await self.attribuer_mission_bouton(interaction, "royal")

@bot.tree.command(name="verifier", description="Entre le code universel pour débloquer l'accès aux fonctionnalités du bot.")
@app_commands.describe(code="Le code universel secret")
async def verifier(interaction: discord.Interaction, code: str):
    config = load_config()
    if not config["enabled"]:
        await interaction.response.send_message("La vérification globale est actuellement désactivée.", ephemeral=True)
        return

    if code == config["verification_code"]:
        role = discord.utils.get(interaction.guild.roles, name="Vérifié")
        if not role:
            try:
                role = await interaction.guild.create_role(name="Vérifié", color=discord.Color.green(), reason="Rôle de vérification automatique")
            except: pass

        if role:
            try:
                await interaction.user.add_roles(role)
                await interaction.response.send_message("✅ Code correct ! Tu es maintenant **Vérifié** et as accès à toutes les fonctionnalités.", ephemeral=True)
                return
            except: pass
        await interaction.response.send_message("✅ Code correct, mais le bot n'a pas pu t'attribuer le rôle (vérifie ses permissions).", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Code incorrect. Réessaie.", ephemeral=True)

@bot.tree.command(name="setcode", description="Change le code universel de vérification (Staff / Propriétaire).")
@app_commands.describe(nouveau_code="Le nouveau code secret")
async def setcode(interaction: discord.Interaction, nouveau_code: str):
    if not verifier_permissions_staff(interaction.user):
        await interaction.response.send_message("❌ Tu n'as pas l'autorisation de changer le code.", ephemeral=True)
        return
    config = load_config()
    config["verification_code"] = nouveau_code
    save_config(config)
    await interaction.response.send_message(f"✅ Le code universel a été mis à jour avec succès : `{nouveau_code}`", ephemeral=True)

@bot.tree.command(name="togglecode", description="Active ou désactive la vérification par code globalement (Staff / Propriétaire).")
async def togglecode(interaction: discord.Interaction):
    if not verifier_permissions_staff(interaction.user):
        await interaction.response.send_message("❌ Tu n'as pas l'autorisation de faire ça.", ephemeral=True)
        return
    config = load_config()
    config["enabled"] = not config["enabled"]
    save_config(config)
    etat = "activée" if config["enabled"] else "désactivée"
    await interaction.response.send_message(f"🔄 Le système de vérification par code est maintenant **{etat}**.", ephemeral=True)

@bot.event
async def on_ready():
    if not verifier_temps_missions.is_running(): verifier_temps_missions.start()
    
    bot.add_view(VueBoutonTicket())
    bot.add_view(VueFermerTicket())
    bot.add_view(VueButinRecupere())
    bot.add_view(VueAccueilArrivant())
    bot.add_view(VueGestionJoueurMission())
    bot.add_view(VueEvaluationMission())
    
    config = load_config()
    if config["enabled"]:
        for guild in bot.guilds:
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).send_messages:
                    try:
                        embed_verif = discord.Embed(
                            title="🔒 Redémarrage de sécurité — Vérification requise",
                            description="Le bot a redémarré. Pour accéder aux fonctionnalités sur ce serveur, entre le code universel via la commande `/verifier <code_universel>`.",
                            color=discord.Color.orange()
                        )
                        await channel.send(embed=embed_verif)
                        break
                    except:
                        pass

    await envoyer_log_proprietaire(bot, f"🚀 **Bot Valerius démarré avec succès !** Connecté et opérationnel.")

    salon_accueil = bot.get_channel(WELCOME_CHANNEL_ID)
    if salon_accueil:
        try:
            async for msg in salon_accueil.history(limit=10):
                if msg.author == bot.user and "Bienvenue" in msg.content:
                    break
            else:
                embed_accueil = discord.Embed(title="⚜️ BIENVENUE ⚜️", description="Veuillez sélectionner ci-dessous votre statut :", color=discord.Color.gold())
                await salon_accueil.send(content="Bienvenue", embed=embed_accueil, view=VueAccueilArrivant())
        except Exception as e:
            print(f"Erreur envoi panneau d'accueil : {e}")

    try:
        synced = await bot.tree.sync()
        print(f"Bot Valerius Pro — {len(synced)} Commandes Slash synchronisées !")
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
            contient_image = False
            if message.attachments:
                for att in message.attachments:
                    if (att.content_type and att.content_type.startswith("image/")) or any(att.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp']):
                        contient_image = True
                        break
            if not contient_image and message.embeds:
                for emb in message.embeds:
                    if emb.image or emb.thumbnail:
                        contient_image = True
                        break

            if contient_image:
                await message.channel.send(f"💬 <@{joueur_id}>, image/preuve bien reçue et transmise aux instructeurs !")
                msg_p = f"📸 **Preuve reçue** pour la mission de <@{joueur_id}>."
                await envoyer_double_notification(message.guild, msg_p, f"📸 Preuve déposée par <@{joueur_id}> dans {message.channel.mention}.", view=VueEvaluationMission(joueur_id), joueur_id=joueur_id)
            else:
                await message.channel.send(f"❌ <@{joueur_id}>, aucune image/photo détectée. Veuillez envoyer une capture valide.")

@bot.tree.command(name="aide", description="Affiche le tableau de bord des quêtes de Valerius.")
async def aide(interaction: discord.Interaction):
    if not verifier_acces_verifie(interaction):
        await interaction.response.send_message("🔒 **Accès refusé !** Tu dois d'abord entrer le code universel avec `/verifier <code_universel>` pour utiliser ce bot.", ephemeral=True)
        return
    await generer_panneau_aide(interaction)

@bot.tree.command(name="help", description="Affiche le tableau de bord des quêtes de Valerius.")
async def help_cmd(interaction: discord.Interaction):
    if not verifier_acces_verifie(interaction):
        await interaction.response.send_message("🔒 **Accès refusé !** Tu dois d'abord entrer le code universel avec `/verifier <code_universel>` pour utiliser ce bot.", ephemeral=True)
        return
    await generer_panneau_aide(interaction)

async def generer_panneau_aide(interaction: discord.Interaction):
    embed = discord.Embed(title="⚜️ TABLEAU DES ORDRES DE VALERIUS ⚜️", color=discord.Color.gold())
    citoyen_desc = "⚔️ **SYSTÈME DE QUÊTES**\n`/missionaccomplie` ↳ Déclarer la fin de ta tâche.\n`/missions_en_cours` ↳ Statut de ton contrat.\n`/tuto` ↳ Guide.\n📊 **ARCHIVES**\n`/historique` ↳ Ton bilan."
    embed.add_field(name="👥 ESPACE DES CITOYENS", value=citoyen_desc, inline=False)
    if verifier_permissions_staff(interaction.user):
        admin_desc = "🚨 **ADMINISTRATION**\n`/openticket` | `/fermerticket` | `/attribuer_mission` | `/export_actives` | `/import_actives` | `/total_backup` | `/total_restore` | `/setcode` | `/togglecode`"
        embed.add_field(name="👑 STAFF", value=admin_desc, inline=False)
    await interaction.response.send_message(embed=embed, view=VueBoutonTicket())

@bot.tree.command(name="tuto", description="Guide d'utilisation pour mener à bien tes décrets.")
async def tuto(interaction: discord.Interaction):
    if not verifier_acces_verifie(interaction):
        await interaction.response.send_message("🔒 **Accès refusé !** Utilise d'abord `/verifier <code_universel>`.", ephemeral=True)
        return
    embed_tuto = discord.Embed(title="🪖 GUIDE DU CITOYEN DE VALERIUS 🪖", description="Utilise `/aide` dans un salon de mission pour ouvrir ton ticket.", color=discord.Color.green())
    await interaction.response.send_message(embed=embed_tuto, ephemeral=True)

@bot.tree.command(name="missions_en_cours", description="Affiche le statut de votre mission active.")
async def missions_en_cours(interaction: discord.Interaction):
    if not verifier_acces_verifie(interaction):
        await interaction.response.send_message("🔒 **Accès refusé !** Utilise d'abord `/verifier <code_universel>`.", ephemeral=True)
        return
    joueur_id = interaction.user.id
    g_id = interaction.guild.id
    if g_id not in missions_actives or joueur_id not in missions_actives[g_id]:
        await interaction.response.send_message("⚪ Tu n'as aucune mission active actuellement sur ce serveur.", ephemeral=True)
        return
    m = missions_actives[g_id][joueur_id]
    ts = int(m["date_fin"].timestamp())
    if m.get("en_attente", False):
        await interaction.response.send_message(f"👤 <@{joueur_id}> [**{m['cat'].upper()}**] -> *\"{m['texte']}\"* 🛑 **GELÉ (En attente d'évaluation)**", ephemeral=True)
    else:
        await interaction.response.send_message(f"👤 <@{joueur_id}> [**{m['cat'].upper()}**] -> *\"{m['texte']}\"* Fin : <t:{ts}:R>", ephemeral=True)

@bot.tree.command(name="missionaccomplie", description="Déclare l'objectif en cours comme accompli.")
async def missionaccomplie(interaction: discord.Interaction):
    if not verifier_acces_verifie(interaction):
        await interaction.response.send_message("🔒 **Accès refusé !** Utilise d'abord `/verifier <code_universel>`.", ephemeral=True)
        return
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
        await interaction.response.send_message(f"💬 {joueur.mention}, demande envoyée aux instructeurs. Chrono gelé.")
        msg_comp = f"📢 {mention_ins} ! {joueur.mention} déclare avoir fini sa mission : *\"{m_info['texte']}\"* !"
        await envoyer_double_notification(interaction.guild, msg_comp, f"📢 {mention_ins} — <@{joueur.id}> a fini sa mission dans {interaction.channel.mention}", view=VueEvaluationMission(joueur.id), joueur_id=joueur.id)
        return
    await interaction.response.send_message("❌ Tu n'as aucune mission active en cours.", ephemeral=True)

@bot.tree.command(name="historique", description="Affiche l'historique de vos décrets passés.")
@app_commands.describe(joueur="Le joueur dont vous voulez voir le casier.")
async def historique(interaction: discord.Interaction, joueur: discord.Member = None):
    if not verifier_acces_verifie(interaction):
        await interaction.response.send_message("🔒 **Accès refusé !** Utilise d'abord `/verifier <code_universel>`.", ephemeral=True)
        return
    cible = joueur or interaction.user
    profils = charger_profils(interaction.guild.id)
    initialiser_profil(cible.id, profils)
    userData = profils[str(cible.id)]
    hist = userData["historique"]
    embed = discord.Embed(title=f"📜 ARCHIVES — {cible.display_name}", color=discord.Color.blue())
    embed.set_thumbnail(url=cible.display_avatar.url)
    embed.add_field(name="📊 Bilan", value=f"🟢 **RÉUSSITES :** `{userData['total_reussies']}`\n🔴 **ÉCHOUÉES :** `{userData['total_echouees']}`", inline=False)
    if not hist:
        embed.add_field(name="📜 Historique", value="*Aucune mission enregistrée.*", inline=False)
    else:
        hist_lignes = []
        for item in hist:
            icone = "✅" if item["statut"] == "Succès" else "❌"
            hist_lignes.append(f"{icone} **[{item['date']}]** `[{item.get('categorie','inconnu').upper()}]` — {item['texte']}")
        corps = "\n".join(hist_lignes)
        if len(corps) > 1024: corps = corps[:1000] + "\n*...*"
        embed.add_field(name="📜 Historique", value=corps, inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="openticket", description="Ouvre un ticket de mission pour un citoyen (Staff).")
@app_commands.describe(joueur="Le citoyen ciblé")
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
    ticket_channel = await guild.create_text_channel(name=f"🪖-ordre-{joueur.name}", overwrites=overwrites, category=interaction.channel.category if interaction.channel.category else None)
    embed_ticket = discord.Embed(title="⚜️ CENTRE DE SÉLECTION DES DÉCRETS ⚜️", description=f"Ticket ouvert pour {joueur.mention}.", color=discord.Color.dark_red())
    await ticket_channel.send(embed=embed_ticket, view=VueChoixDifficulte(joueur.id))
    asyncio.create_task(gerer_expiration_automatique(guild, ticket_channel.id, joueur.id))
    await interaction.followup.send(f"✅ Ticket créé : {ticket_channel.mention}", ephemeral=True)

@bot.tree.command(name="fermerticket", description="Ferme et supprime le salon actuel (Staff).")
async def fermerticket(interaction: discord.Interaction):
    if not verifier_permissions_staff(interaction.user):
        await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        return
    await interaction.response.send_message("⚙️ Fermeture du salon...", ephemeral=True)
    g_id = interaction.guild.id
    if g_id in missions_actives:
        for j_id, m_info in list(missions_actives[g_id].items()):
            if m_info.get("channel_id") == interaction.channel.id or f"🪖-ordre-" in interaction.channel.name:
                del missions_actives[g_id][j_id]
                break
    try: await interaction.channel.delete()
    except: pass

@bot.tree.command(name="attribuer_mission", description="Attribue une mission à un joueur (Staff).")
@app_commands.describe(joueur="Le citoyen", categorie="commune, moyenne, difficile, royal")
async def attribuer_mission(interaction: discord.Interaction, joueur: discord.Member, categorie: str):
    if not verifier_permissions_staff(interaction.user):
        await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        return
    cat = categorie.lower().strip()
    if cat in ["commun"]: cat = "commune"
    elif cat in ["moyen"]: cat = "moyenne"
    if cat not in ["commune", "moyenne", "difficile", "royal"]:
        await interaction.response.send_message("❌ Catégorie invalide.", ephemeral=True)
        return
    guild_id = interaction.guild.id
    if guild_id not in missions_actives: missions_actives[guild_id] = {}
    if joueur.id in missions_actives[guild_id]:
        await interaction.response.send_message("❌ Mission active existante.", ephemeral=True)
        return
    missions_dispo = charger_missions_fichier(guild_id)
    if not missions_dispo[cat]:
        await interaction.response.send_message("❌ Plus de mission dans cette catégorie.", ephemeral=True)
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
    embed_mission = discord.Embed(title="📜 DÉCRET IMPÉRIAL ATTRIBUÉ", color=discord.Color.gold())
    embed_mission.add_field(name="🎯 Objectif", value=f"*{mission_choisie['texte']}*", inline=False)
    embed_mission.add_field(name="⏳ Temps", value=f"<t:{timestamp_discord}:R>", inline=False)
    await interaction.response.send_message(content=f"✅ Mission attribuée à {joueur.mention} !", embed=embed_mission, view=VueGestionJoueurMission(joueur.id))

@bot.tree.command(name="export_actives", description="Exporte les missions en cours (Staff).")
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
    contenu_json = json.dumps(actives_serveur, indent=4, ensure_ascii=False)
    buffer = io.BytesIO(contenu_json.encode("utf-8"))
    buffer.seek(0)
    await interaction.response.send_message("📤 **Sauvegarde :**", file=discord.File(buffer, filename=f"missions_actives_{guild_id}.txt"), ephemeral=True)

@bot.tree.command(name="import_actives", description="Restaure les missions en cours (Staff).")
@app_commands.describe(fichier="Fichier txt des missions actives")
async def import_actives(interaction: discord.Interaction, fichier: discord.Attachment):
    if not verifier_permissions_staff(interaction.user):
        await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    guild_id = interaction.guild.id
    if guild_id not in missions_actives: missions_actives[guild_id] = {}
    try:
        contenu_bytes = await fichier.read()
        donnees = json.loads(contenu_bytes.decode("utf-8"))
        nb = 0
        for str_j_id, m_data in donnees.items():
            if not str_j_id.isdigit(): continue
            j_id = int(str_j_id)
            missions_actives[guild_id][j_id] = {
                "texte": m_data["texte"], "delai_texte": m_data["delai_texte"],
                "date_debut": datetime.fromisoformat(m_data["date_debut"]),
                "date_fin": datetime.fromisoformat(m_data["date_fin"]),
                "duree_totale": timedelta(seconds=m_data["duree_totale_seconds"]),
                "cat": m_data["cat"], "channel_id": m_data["channel_id"],
                "alerte_moitie": m_data["alerte_moitie"], "alerte_un_quart": m_data["alerte_un_quart"],
                "en_attente": m_data["en_attente"]
            }
            nb += 1
        await interaction.followup.send(f"✅ {nb} missions en cours réinjectées !", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Erreur : {e}", ephemeral=True)

@bot.tree.command(name="total_backup", description="Sauvegarde globale (Staff).")
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
    for f_path in glob.glob("valerius_missions_*.txt") + glob.glob("valerius_profils_*.json") + [CONFIG_FILE]:
        if os.path.exists(f_path):
            with open(f_path, "r", encoding="utf-8") as f:
                donnees_globales["fichiers_disques"][f_path] = f.read()
    buffer = io.BytesIO(json.dumps(donnees_globales, indent=4, ensure_ascii=False).encode("utf-8"))
    buffer.seek(0)
    await interaction.followup.send("📦 **Backup total :**", file=discord.File(buffer, filename=f"total_backup_{datetime.now().strftime('%Y-%m-%d')}.json"), ephemeral=True)

@bot.tree.command(name="total_restore", description="Restauration globale (Staff).")
@app_commands.describe(fichier="Fichier de backup json")
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
            for str_j_id, m_data in j_dict.items():
                missions_actives[g_id][int(str_j_id)] = {
                    "texte": m_data["texte"], "delai_texte": m_data["delai_texte"],
                    "date_debut": datetime.fromisoformat(m_data["date_debut"]),
                    "date_fin": datetime.fromisoformat(m_data["date_fin"]),
                    "duree_totale": timedelta(seconds=m_data["duree_totale_seconds"]),
                    "cat": m_data["cat"], "channel_id": m_data["channel_id"],
                    "alerte_moitie": m_data["alerte_moitie"], "alerte_un_quart": m_data["alerte_un_quart"],
                    "en_attente": m_data["en_attente"]
                }
        await interaction.followup.send("✅ **Restauration réussie !**", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Erreur : {e}", ephemeral=True)

@bot.tree.command(name="ajouterhistorique", description="Ajoute une entrée dans l'historique (Staff).")
@app_commands.describe(joueur="Le citoyen", statut="Succès ou Echec", categorie="commune, moyenne, difficile, royal", texte="Description")
@app_commands.choices(statut=[app_commands.Choice(name="Succès", value="Succès"), app_commands.Choice(name="Echec", value="Échec")])
@app_commands.choices(categorie=[app_commands.Choice(name="Commune", value="commune"), app_commands.Choice(name="Moyenne", value="moyenne"), app_commands.Choice(name="Difficile", value="difficile"), app_commands.Choice(name="Royal", value="royal")])
async def ajouterhistorique(interaction: discord.Interaction, joueur: discord.Member, statut: str, categorie: str, texte: str):
    if not verifier_permissions_staff(interaction.user):
        await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        return
    g_id = interaction.guild.id
    profils = charger_profils(g_id)
    initialiser_profil(joueur.id, profils)
    if statut == "Succès": profils[str(joueur.id)]["total_reussies"] += 1
    else: profils[str(joueur.id)]["total_echouees"] += 1
    ajouter_historique(joueur.id, profils, texte, statut, categorie)
    sauvegarder_profils(g_id, profils)
    await interaction.response.send_message(f"✅ Ajouté dans l'historique de {joueur.mention} !", ephemeral=True)

@bot.tree.command(name="mission_expiration", description="Lance l'alerte d'expiration (Staff).")
@app_commands.describe(joueur="Le citoyen")
async def mission_expiration(interaction: discord.Interaction, joueur: discord.Member):
    if not verifier_permissions_staff(interaction.user):
        await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        return
    g_id = interaction.guild.id
    if g_id in missions_actives and joueur.id in missions_actives[g_id]:
        await interaction.response.send_message("❌ Mission déjà en cours.", ephemeral=True)
        return
    expiration_time = int((datetime.now() + timedelta(hours=1)).timestamp())
    await interaction.response.send_message(f"⚠️ {joueur.mention}, cet ordre va expirer <t:{expiration_time}:R>.")

keep_alive()
bot.run("TON_TOKEN_DISCORD")
