from app.main import main

if __name__ == "__main__":
    import sys

    sys.argv.extend(["--mode", "tcp"]) if "--mode" not in sys.argv else None
    main()
