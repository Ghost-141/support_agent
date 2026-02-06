import uvicorn


def main() -> None:
    uvicorn.run(
        "api.app:app",
        host="0.0.0.0",
        port=80,
        loop="api.uvicorn_loop:selector_loop_factory",
    )


if __name__ == "__main__":
    main()
