# migrate_clean_image_paths.py

from main import app, db, Item
from urllib.parse import urlparse, unquote

def clean_image_filenames():
    with app.app_context():
        items = Item.query.all()
        updated_count = 0

        for item in items:
            if not item.image_filenames:
                continue

            cleaned_paths = []
            for entry in item.image_filenames.split(','):
                entry = entry.strip()

                # If it's a full URL → extract path after '/object/sign/'
                if entry.startswith("http"):
                    try:
                        parsed = urlparse(entry)
                        path_part = parsed.path

                        # Example path: /storage/v1/object/sign/images/uploads/xxxx.jpg
                        # We want: uploads/xxxx.jpg
                        prefix = "/storage/v1/object/sign/images/"
                        if prefix in path_part:
                            path_after_prefix = path_part.split(prefix, 1)[1]
                            path_after_prefix = unquote(path_after_prefix)  # URL decode
                            cleaned_paths.append(path_after_prefix)
                            continue
                    except Exception as e:
                        print(f"Error parsing URL: {entry}, error: {e}")

                # If already looks like a path → keep it
                cleaned_paths.append(entry)

            # If any changes → update the item
            new_image_filenames = ",".join(cleaned_paths)
            if new_image_filenames != item.image_filenames:
                print(f"[Item {item.id}] Updating image_filenames.")
                item.image_filenames = new_image_filenames
                updated_count += 1

        if updated_count > 0:
            db.session.commit()
            print(f"✅ Migration complete: {updated_count} items updated.")
        else:
            print("✅ Migration complete: No updates needed (already clean).")

if __name__ == "__main__":
    clean_image_filenames()
