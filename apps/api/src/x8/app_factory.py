from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from x8.api.routes import approvals, artifacts, attachments, audit, avatar, brain, brain_health, capabilities, chat, config_import, continuity, docker_commands, github, health, images, integrations, local_bridge, memory, models, operator, receipts, search, self_build, sessions, speech, team, visual_git_proof, workspace
from x8.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()
    app = FastAPI(title="XV8 API", version="0.1.0")
    app.state.settings = config
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for router in (
        health.router,
        capabilities.router,
        integrations.router,
        github.router,
        workspace.router,
        docker_commands.router,
        local_bridge.router,
        search.router,
        images.router,
        config_import.router,
        avatar.router,
        speech.router,
        approvals.router,
        operator.router,
        team.router,
        attachments.router,
        chat.router,
        visual_git_proof.router,
        self_build.router,
        sessions.router,
        brain.router,
        brain_health.router,
        continuity.router,
        memory.router,
        models.router,
        receipts.router,
        artifacts.router,
        audit.router,
    ):
        app.include_router(router)
    return app
