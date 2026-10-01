"""Resolve account and member partitions through authenticated ownership."""
from fastapi import HTTPException
from app.models.nexus import FamilyMemberDB


async def resolve_private_scope(requested, user, db):
    if user is None:
        raise HTTPException(401, 'Authentication required')
    if requested in (None, '', 'default', user.user_id):
        return user.user_id
    if requested.startswith('member_'):
        member = await db.get(FamilyMemberDB, requested[len('member_'):])
        if member is not None and member.user_id == user.user_id:
            return requested
    raise HTTPException(403, 'This data partition is not linked to your account')
