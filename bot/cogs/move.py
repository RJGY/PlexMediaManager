import discord
from discord import app_commands # Added
from discord.ext import commands
import logging # Added for error logging
import os
import pathlib
from typing import Optional


class Move(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_folder_structure(self, path: str, max_depth: int = 3, current_depth: int = 0) -> str:
        """Generate a visual representation of folder structure."""
        try:
            path_obj = pathlib.Path(path)
            if not path_obj.exists() or not path_obj.is_dir():
                return f"❌ Path does not exist or is not a directory: {path}"
            
            if current_depth >= max_depth:
                return "  " * current_depth + "└── ... (max depth reached)"
            
            structure = []
            if current_depth == 0:
                structure.append(f"📁 {path_obj.name or path_obj}")
            
            try:
                items = sorted(path_obj.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
                for i, item in enumerate(items[:20]):  # Limit to 20 items per folder
                    is_last = i == len(items) - 1 or i == 19
                    prefix = "└── " if is_last else "├── "
                    indent = "  " * current_depth
                    
                    if item.is_dir():
                        structure.append(f"{indent}{prefix}📁 {item.name}")
                        if current_depth < max_depth - 1:
                            sub_structure = self.get_folder_structure(str(item), max_depth, current_depth + 1)
                            structure.append(sub_structure)
                    else:
                        structure.append(f"{indent}{prefix}📄 {item.name}")
                
                if len(items) > 20:
                    structure.append("  " * current_depth + "└── ... (more items)")
                    
            except PermissionError:
                structure.append("  " * current_depth + "└── ❌ Permission denied")
            
            return "\n".join(structure)
            
        except Exception as e:
            return f"❌ Error reading folder structure: {str(e)}"

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handles errors for app commands in this cog."""
        logging.error(f"Error in Move cog, command '{interaction.command.name if interaction.command else 'Unknown'}': {error}", exc_info=error)
        ephemeral = True
        message = f"An unexpected error occurred: {error}"

        # Example for custom errors if they were defined for torrenting:
        # if isinstance(error.original, TorrentSpecificError):
        #     message = str(error.original)

        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=ephemeral)
        else:
            try:
                await interaction.response.send_message(message, ephemeral=ephemeral)
            except discord.errors.InteractionResponded:
                await interaction.followup.send(message, ephemeral=ephemeral)
            except Exception as e:
                logging.error(f"Failed to send error message for Torrent cog: {e}")

    @app_commands.command(name="move", description="Moves a file to a new location with folder structure preview.")
    @app_commands.describe(
        file="The file to move.",
        location="The location to move the file to (e.g., 'C:\\Users\\Reese\\Downloads').",
        show_structure="Whether to show the folder structure of the destination (default: True)."
    )
    async def move_command(self, interaction: discord.Interaction, file: str, location: str, show_structure: bool = True):
        """Move a file to another folder with optional folder structure preview."""
        await interaction.response.defer()
        
        try:
            # Validate paths
            source_path = pathlib.Path(file)
            dest_path = pathlib.Path(location)
            
            if not source_path.exists():
                await interaction.followup.send(f"❌ Source file does not exist: `{file}`", ephemeral=True)
                return
            
            if not dest_path.exists() or not dest_path.is_dir():
                await interaction.followup.send(f"❌ Destination directory does not exist: `{location}`", ephemeral=True)
                return
            
            # Create embed for the response
            embed = discord.Embed(
                title="📁 File Move Operation",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            
            embed.add_field(
                name="📄 Source File",
                value=f"`{source_path.name}`",
                inline=True
            )
            
            embed.add_field(
                name="📁 Destination",
                value=f"`{dest_path}`",
                inline=True
            )
            
            # Show folder structure if requested
            if show_structure:
                structure = self.get_folder_structure(str(dest_path), max_depth=2)
                
                # Discord has a 1024 character limit for embed field values
                if len(structure) > 1000:
                    structure = structure[:997] + "..."
                
                embed.add_field(
                    name="📂 Destination Folder Structure",
                    value=f"```\n{structure}\n```",
                    inline=False
                )
            
            # Add confirmation message
            embed.add_field(
                name="⚠️ Confirmation",
                value="This is a preview. The actual move operation is not yet implemented.",
                inline=False
            )
            
            embed.set_footer(text="Use show_structure=False to hide the folder structure")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            logging.error(f"Error in move command: {e}")
            await interaction.followup.send(f"❌ An error occurred: {str(e)}", ephemeral=True)



async def setup(bot):
    await bot.add_cog(Move(bot))