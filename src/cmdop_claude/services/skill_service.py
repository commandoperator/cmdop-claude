"""Skill service."""
import shutil
from pathlib import Path
from typing import Optional

import frontmatter

from cmdop_claude._config import Config
from cmdop_claude.models.skill import SkillFrontmatter
from cmdop_claude.services.base import BaseService

class SkillService(BaseService):
    """Service for managing SKILL.md files."""

    __slots__ = ("_skills_dir",)

    def __init__(self, config: Config) -> None:
        super().__init__(config)
        self._skills_dir = Path(self._config.claude_dir_path) / "skills"

    def get_skill(self, skill_dir_name: str) -> Optional[SkillFrontmatter]:
        """Read a single skill's frontmatter."""
        skill_path = self._skills_dir / skill_dir_name / "SKILL.md"
        if not skill_path.exists():
            return None
        
        post = frontmatter.load(str(skill_path))
        return SkillFrontmatter.model_validate(post.metadata)
    
    def list_skills(self) -> dict[str, SkillFrontmatter]:
        """List all available skills."""
        if not self._skills_dir.exists():
            return {}
            
        skills = {}
        for skill_dir in self._skills_dir.iterdir():
            if skill_dir.is_dir():
                skill = self.get_skill(skill_dir.name)
                if skill is not None:
                    skills[skill_dir.name] = skill
        return skills
    
    def get_skill_dir_path(self, skill_dir_name: str) -> Path:
        """Get the absolute path to a skill directory."""
        return self._skills_dir / skill_dir_name

    def get_skill_content(self, skill_dir_name: str) -> str:
        """Get the markdown body of a skill."""
        skill_path = self._skills_dir / skill_dir_name / "SKILL.md"
        if not skill_path.exists():
            return ""
        post = frontmatter.load(str(skill_path))
        return post.content
        
    def update_skill_content(self, skill_dir_name: str, content: str) -> None:
        """Update the markdown body of a skill."""
        skill_path = self._skills_dir / skill_dir_name / "SKILL.md"
        if not skill_path.exists():
            raise FileNotFoundError(f"SKILL.md not found in {skill_dir_name}")
        post = frontmatter.load(str(skill_path))
        post.content = content
        skill_path.write_text(frontmatter.dumps(post), encoding="utf-8")

    def create_skill(self, name: str, description: str = "") -> None:
        """Create a new skill directory with a boilerplate SKILL.md."""
        # Convert name to safe directory name
        dir_name = "".join([c if c.isalnum() else "_" for c in name.lower()])
        skill_path_dir = self._skills_dir / dir_name
        skill_path_dir.mkdir(parents=True, exist_ok=True)
        
        skill_path = skill_path_dir / "SKILL.md"
        if skill_path.exists():
            raise FileExistsError(f"Skill {dir_name} already exists.")
            
        post = frontmatter.Post(
            "Write your instructions here...",
            name=name,
            description=description,
            **{"allowed-tools": ["Read", "Write"]},
            **{"disable-model-invocation": False}
        )
        skill_path.write_text(frontmatter.dumps(post), encoding="utf-8")

    def update_skill(self, skill_dir_name: str, data: SkillFrontmatter) -> None:
        """Update a skill's frontmatter."""
        skill_path = self._skills_dir / skill_dir_name / "SKILL.md"
        if not skill_path.exists():
            raise FileNotFoundError(f"SKILL.md not found in {skill_dir_name}")

        post = frontmatter.load(str(skill_path))
        post.metadata = data.model_dump(by_alias=True, exclude_none=True)
        skill_path.write_text(frontmatter.dumps(post), encoding="utf-8")

    def search_skills(self, query: str) -> dict[str, SkillFrontmatter]:
        """Filter skills by name or description (case-insensitive)."""
        q = query.lower()
        return {
            name: skill
            for name, skill in self.list_skills().items()
            if q in (skill.name or "").lower() or q in (skill.description or "").lower()
        }

    def import_from_path(self, src: str) -> str:
        """Copy a skill folder from a local path into ~/.claude/skills/.

        Returns the skill directory name.
        Raises ValueError if no SKILL.md found.
        Raises FileExistsError if skill already installed.
        """
        src_path = Path(src).expanduser().resolve()
        if not (src_path / "SKILL.md").exists():
            raise ValueError(f"No SKILL.md found in {src_path}")
        dest = self._skills_dir / src_path.name
        if dest.exists():
            raise FileExistsError(f"Skill '{src_path.name}' already installed.")
        self._skills_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src_path, dest)
        return src_path.name
