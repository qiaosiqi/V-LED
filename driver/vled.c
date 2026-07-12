#include <linux/cdev.h>
#include <linux/device.h>
#include <linux/err.h>
#include <linux/fs.h>
#include <linux/init.h>
#include <linux/kernel.h>
#include <linux/mm.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/slab.h>
#include <linux/string.h>
#include <linux/uaccess.h>
#include <linux/version.h>

#define VLED_DEVICE_NAME "vled"
#define VLED_CLASS_NAME "vled"
#define VLED_DEFAULT_WIDTH 32
#define VLED_DEFAULT_HEIGHT 16
#define VLED_TEXT_MAX 1024
#define VLED_MODE_MAX 8
#define VLED_ESCAPED_TEXT_MAX (VLED_TEXT_MAX * 2 + 1)

struct vled_state {
	int width;
	int height;
	char text[VLED_TEXT_MAX];
	int red;
	int green;
	int blue;
	int brightness;
	char mode[VLED_MODE_MAX];
	unsigned long version;
};

struct vled_device {
	dev_t devno;
	struct cdev cdev;
	struct class *class;
	struct device *device;
	struct mutex lock;
	char buffer[PAGE_SIZE];
	size_t buffer_len;
	struct vled_state state;
};

struct vled_file_context {
	struct mutex lock;
	loff_t read_offset;
	size_t write_offset;
	char *read_snapshot;
	size_t read_snapshot_len;
	unsigned long read_snapshot_version;
	bool read_snapshot_valid;
	char *write_buffer;
};

static struct vled_device vled;

static void vled_reset_state(void)
{
	memset(&vled.state, 0, sizeof(vled.state));
	vled.state.width = VLED_DEFAULT_WIDTH;
	vled.state.height = VLED_DEFAULT_HEIGHT;
	vled.state.red = 255;
	vled.state.green = 255;
	vled.state.blue = 255;
	vled.state.brightness = 100;
	strscpy(vled.state.mode, "static", sizeof(vled.state.mode));
	memset(vled.buffer, 0, sizeof(vled.buffer));
	vled.buffer_len = 0;
}

static void vled_strip_line_end(char *value)
{
	size_t len;

	len = strlen(value);
	while (len > 0 && (value[len - 1] == '\n' || value[len - 1] == '\r'))
		value[--len] = '\0';
}

static char *vled_skip_blanks(char *value)
{
	while (*value == ' ' || *value == '\t')
		value++;
	return value;
}

static bool vled_has_command(const char *value, const char *command)
{
	size_t len = strlen(command);

	return strncmp(value, command, len) == 0 &&
	       (value[len] == '\0' || value[len] == ' ' || value[len] == '\t');
}

static bool vled_valid_color(int value)
{
	return value >= 0 && value <= 255;
}

static int vled_parse_command(const struct vled_state *current_state,
			      char *raw_command, struct vled_state *next,
			      bool *changed)
{
	char *command = vled_skip_blanks(raw_command);
	char *arg;
	int red;
	int green;
	int blue;
	int brightness;
	char mode[VLED_MODE_MAX];
	char tail;

	*next = *current_state;
	*changed = false;

	if (*command == '\0')
		return -EINVAL;

	if (vled_has_command(command, "TEXT")) {
		arg = vled_skip_blanks(command + strlen("TEXT"));
		if (strlen(arg) >= sizeof(next->text))
			return -EMSGSIZE;

		if (strcmp(next->text, arg) != 0) {
			strscpy(next->text, arg, sizeof(next->text));
			*changed = true;
		}
		return 0;
	}

	if (vled_has_command(command, "COLOR")) {
		arg = strim(command + strlen("COLOR"));
		if (sscanf(arg, "%d %d %d%c", &red, &green, &blue, &tail) != 3)
			return -EINVAL;
		if (!vled_valid_color(red) || !vled_valid_color(green) ||
		    !vled_valid_color(blue))
			return -EINVAL;

		if (next->red != red || next->green != green || next->blue != blue) {
			next->red = red;
			next->green = green;
			next->blue = blue;
			*changed = true;
		}
		return 0;
	}

	if (vled_has_command(command, "BRIGHTNESS")) {
		arg = strim(command + strlen("BRIGHTNESS"));
		if (sscanf(arg, "%d%c", &brightness, &tail) != 1)
			return -EINVAL;
		if (brightness < 0 || brightness > 100)
			return -EINVAL;

		if (next->brightness != brightness) {
			next->brightness = brightness;
			*changed = true;
		}
		return 0;
	}

	if (vled_has_command(command, "MODE")) {
		arg = strim(command + strlen("MODE"));
		if (sscanf(arg, "%7s%c", mode, &tail) != 1)
			return -EINVAL;
		if (strcmp(mode, "static") != 0 && strcmp(mode, "scroll") != 0)
			return -EINVAL;

		if (strcmp(next->mode, mode) != 0) {
			strscpy(next->mode, mode, sizeof(next->mode));
			*changed = true;
		}
		return 0;
	}

	command = strim(command);
	if (strcmp(command, "CLEAR") == 0) {
		if (next->text[0] != '\0') {
			next->text[0] = '\0';
			*changed = true;
		}
		return 0;
	}

	if (strcmp(command, "STATUS") == 0)
		return 0;

	if (vled_has_command(command, "PIXEL"))
		return -EOPNOTSUPP;

	return -EINVAL;
}

static int vled_json_escape(const char *src, char *dst, size_t dst_size)
{
	size_t in = 0;
	size_t out = 0;
	unsigned char ch;

	if (dst_size == 0)
		return -EMSGSIZE;

	while (src[in] != '\0') {
		ch = src[in++];

		switch (ch) {
		case '"':
		case '\\':
		case '\n':
		case '\r':
		case '\t':
			if (out + 2 >= dst_size)
				return -EMSGSIZE;
			dst[out++] = '\\';
			switch (ch) {
			case '\n':
				dst[out++] = 'n';
				break;
			case '\r':
				dst[out++] = 'r';
				break;
			case '\t':
				dst[out++] = 't';
				break;
			default:
				dst[out++] = ch;
				break;
			}
			break;
		default:
			if (out + 1 >= dst_size)
				return -EMSGSIZE;
			/* Other JSON control bytes are normalized deterministically. */
			dst[out++] = ch < 0x20 ? ' ' : ch;
			break;
		}
	}

	dst[out] = '\0';
	return 0;
}

static int vled_build_json(const struct vled_state *state, char *dst,
			   size_t dst_size, char *escaped_text,
			   size_t escaped_size)
{
	int ret;
	int written;

	ret = vled_json_escape(state->text, escaped_text, escaped_size);
	if (ret)
		return ret;

	written = snprintf(dst, dst_size,
			   "{\"type\":\"state\",\"width\":%d,\"height\":%d,"
			   "\"text\":\"%s\",\"color\":[%d,%d,%d],"
			   "\"brightness\":%d,\"mode\":\"%s\",\"version\":%lu}",
			   state->width, state->height, escaped_text,
			   state->red, state->green, state->blue,
			   state->brightness, state->mode, state->version);
	if (written < 0)
		return written;
	if ((size_t)written >= dst_size)
		return -EMSGSIZE;
	return written;
}

static int vled_open(struct inode *inode, struct file *file)
{
	struct vled_file_context *ctx;
	int ret;

	ret = nonseekable_open(inode, file);
	if (ret)
		return ret;

	ctx = kzalloc(sizeof(*ctx), GFP_KERNEL);
	if (!ctx)
		return -ENOMEM;

	ctx->read_snapshot = kzalloc(PAGE_SIZE, GFP_KERNEL);
	if (!ctx->read_snapshot) {
		kfree(ctx);
		return -ENOMEM;
	}

	ctx->write_buffer = kzalloc(PAGE_SIZE, GFP_KERNEL);
	if (!ctx->write_buffer) {
		kfree(ctx->read_snapshot);
		kfree(ctx);
		return -ENOMEM;
	}

	mutex_init(&ctx->lock);
	file->private_data = ctx;
	return 0;
}

static int vled_release(struct inode *inode, struct file *file)
{
	struct vled_file_context *ctx = file->private_data;

	(void)inode;
	if (ctx) {
		kfree(ctx->write_buffer);
		kfree(ctx->read_snapshot);
		kfree(ctx);
	}
	file->private_data = NULL;
	return 0;
}

static ssize_t vled_read(struct file *file, char __user *user_buf,
			 size_t count, loff_t *ppos)
{
	struct vled_file_context *ctx = file->private_data;
	ssize_t ret;

	(void)ppos;
	if (!ctx)
		return -EIO;
	if (count == 0)
		return 0;

	mutex_lock(&ctx->lock);
	if (!ctx->read_snapshot_valid) {
		mutex_lock(&vled.lock);
		memcpy(ctx->read_snapshot, vled.buffer, vled.buffer_len);
		ctx->read_snapshot[vled.buffer_len] = '\0';
		ctx->read_snapshot_len = vled.buffer_len;
		ctx->read_snapshot_version = vled.state.version;
		ctx->read_offset = 0;
		ctx->read_snapshot_valid = true;
		mutex_unlock(&vled.lock);
	}

	ret = simple_read_from_buffer(user_buf, count, &ctx->read_offset,
				      ctx->read_snapshot,
				      ctx->read_snapshot_len);
	mutex_unlock(&ctx->lock);
	return ret;
}

static ssize_t vled_write(struct file *file, const char __user *user_buf,
			  size_t count, loff_t *ppos)
{
	struct vled_file_context *ctx = file->private_data;
	struct vled_state candidate;
	char *escaped_text;
	char *new_json;
	char *command;
	size_t old_offset;
	bool changed;
	int json_len;
	ssize_t ret;

	(void)ppos;
	if (!ctx)
		return -EIO;
	if (count == 0)
		return 0;
	if (count >= PAGE_SIZE)
		return -EMSGSIZE;

	new_json = kzalloc(PAGE_SIZE, GFP_KERNEL);
	if (!new_json)
		return -ENOMEM;
	escaped_text = kzalloc(VLED_ESCAPED_TEXT_MAX, GFP_KERNEL);
	if (!escaped_text) {
		kfree(new_json);
		return -ENOMEM;
	}

	mutex_lock(&ctx->lock);
	if (ctx->write_offset >= PAGE_SIZE ||
	    count >= PAGE_SIZE - ctx->write_offset) {
		ret = -ENOSPC;
		goto unlock_context;
	}

	old_offset = ctx->write_offset;
	if (copy_from_user(ctx->write_buffer + old_offset, user_buf, count)) {
		memset(ctx->write_buffer + old_offset, 0, count + 1);
		ret = -EFAULT;
		goto unlock_context;
	}
	ctx->write_buffer[old_offset + count] = '\0';
	command = ctx->write_buffer + old_offset;
	vled_strip_line_end(command);

	mutex_lock(&vled.lock);
	ret = vled_parse_command(&vled.state, command, &candidate, &changed);
	if (ret)
		goto rollback_locked;

	if (changed)
		candidate.version = vled.state.version + 1;
	json_len = vled_build_json(&candidate, new_json, PAGE_SIZE,
				   escaped_text, VLED_ESCAPED_TEXT_MAX);
	if (json_len < 0) {
		ret = json_len;
		goto rollback_locked;
	}

	vled.state = candidate;
	memset(vled.buffer, 0, sizeof(vled.buffer));
	memcpy(vled.buffer, new_json, (size_t)json_len);
	vled.buffer_len = json_len;
	ctx->write_offset = old_offset + count;
	ctx->read_offset = 0;
	ctx->read_snapshot_len = 0;
	ctx->read_snapshot_version = 0;
	ctx->read_snapshot_valid = false;
	mutex_unlock(&vled.lock);
	ret = count;
	goto unlock_context;

rollback_locked:
	memset(ctx->write_buffer + old_offset, 0, count + 1);
	mutex_unlock(&vled.lock);
unlock_context:
	mutex_unlock(&ctx->lock);
	kfree(escaped_text);
	kfree(new_json);
	return ret;
}

static const struct file_operations vled_fops = {
	.owner = THIS_MODULE,
	.open = vled_open,
	.read = vled_read,
	.write = vled_write,
	.release = vled_release,
};

static int __init vled_init(void)
{
	char *escaped_text;
	int json_len;
	int ret;

	mutex_init(&vled.lock);
	vled_reset_state();

	escaped_text = kzalloc(VLED_ESCAPED_TEXT_MAX, GFP_KERNEL);
	if (!escaped_text)
		return -ENOMEM;
	json_len = vled_build_json(&vled.state, vled.buffer,
				   sizeof(vled.buffer), escaped_text,
				   VLED_ESCAPED_TEXT_MAX);
	kfree(escaped_text);
	if (json_len < 0)
		return json_len;
	vled.buffer_len = json_len;

	ret = alloc_chrdev_region(&vled.devno, 0, 1, VLED_DEVICE_NAME);
	if (ret)
		return ret;

	cdev_init(&vled.cdev, &vled_fops);
	vled.cdev.owner = THIS_MODULE;

	ret = cdev_add(&vled.cdev, vled.devno, 1);
	if (ret)
		goto unregister_region;

#if LINUX_VERSION_CODE >= KERNEL_VERSION(6, 4, 0)
	vled.class = class_create(VLED_CLASS_NAME);
#else
	vled.class = class_create(THIS_MODULE, VLED_CLASS_NAME);
#endif
	if (IS_ERR(vled.class)) {
		ret = PTR_ERR(vled.class);
		goto del_cdev;
	}

	vled.device = device_create(vled.class, NULL, vled.devno, NULL,
				    VLED_DEVICE_NAME);
	if (IS_ERR(vled.device)) {
		ret = PTR_ERR(vled.device);
		goto destroy_class;
	}

	pr_info("vled: registered /dev/%s major=%d minor=%d\n",
		VLED_DEVICE_NAME, MAJOR(vled.devno), MINOR(vled.devno));
	return 0;

destroy_class:
	class_destroy(vled.class);
del_cdev:
	cdev_del(&vled.cdev);
unregister_region:
	unregister_chrdev_region(vled.devno, 1);
	return ret;
}

static void __exit vled_exit(void)
{
	device_destroy(vled.class, vled.devno);
	class_destroy(vled.class);
	cdev_del(&vled.cdev);
	unregister_chrdev_region(vled.devno, 1);
	pr_info("vled: unregistered /dev/%s\n", VLED_DEVICE_NAME);
}

module_init(vled_init);
module_exit(vled_exit);

MODULE_LICENSE("GPL");
MODULE_AUTHOR("VLED Team Member A");
MODULE_DESCRIPTION("Virtual LED Linux character device driver");
