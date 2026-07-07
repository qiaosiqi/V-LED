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
	loff_t read_offset;
	loff_t write_offset;
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

static int vled_apply_command_locked(char *raw_command)
{
	char *command = vled_skip_blanks(raw_command);
	char *arg;
	int red;
	int green;
	int blue;
	int brightness;
	char mode[VLED_MODE_MAX];
	char tail;

	if (*command == '\0')
		return -EINVAL;

	if (vled_has_command(command, "TEXT")) {
		arg = vled_skip_blanks(command + strlen("TEXT"));
		if (strlen(arg) >= sizeof(vled.state.text))
			return -EMSGSIZE;

		strscpy(vled.state.text, arg, sizeof(vled.state.text));
		vled.state.version++;
		return 0;
	}

	if (vled_has_command(command, "COLOR")) {
		arg = strim(command + strlen("COLOR"));
		if (sscanf(arg, "%d %d %d%c", &red, &green, &blue, &tail) != 3)
			return -EINVAL;
		if (!vled_valid_color(red) || !vled_valid_color(green) ||
		    !vled_valid_color(blue))
			return -EINVAL;

		vled.state.red = red;
		vled.state.green = green;
		vled.state.blue = blue;
		vled.state.version++;
		return 0;
	}

	if (vled_has_command(command, "BRIGHTNESS")) {
		arg = strim(command + strlen("BRIGHTNESS"));
		if (sscanf(arg, "%d%c", &brightness, &tail) != 1)
			return -EINVAL;
		if (brightness < 0 || brightness > 100)
			return -EINVAL;

		vled.state.brightness = brightness;
		vled.state.version++;
		return 0;
	}

	if (vled_has_command(command, "MODE")) {
		arg = strim(command + strlen("MODE"));
		if (sscanf(arg, "%7s%c", mode, &tail) != 1)
			return -EINVAL;
		if (strcmp(mode, "static") != 0 && strcmp(mode, "scroll") != 0)
			return -EINVAL;

		strscpy(vled.state.mode, mode, sizeof(vled.state.mode));
		vled.state.version++;
		return 0;
	}

	command = strim(command);
	if (strcmp(command, "CLEAR") == 0) {
		vled.state.text[0] = '\0';
		vled.state.version++;
		return 0;
	}

	if (strcmp(command, "STATUS") == 0)
		return 0;

	if (vled_has_command(command, "PIXEL"))
		return -EOPNOTSUPP;

	return -EINVAL;
}

static void vled_json_escape(const char *src, char *dst, size_t dst_size)
{
	size_t in = 0;
	size_t out = 0;
	unsigned char ch;

	if (dst_size == 0)
		return;

	while (src[in] != '\0' && out + 1 < dst_size) {
		ch = src[in++];

		switch (ch) {
		case '"':
		case '\\':
			if (out + 2 >= dst_size)
				goto done;
			dst[out++] = '\\';
			dst[out++] = ch;
			break;
		case '\n':
			if (out + 2 >= dst_size)
				goto done;
			dst[out++] = '\\';
			dst[out++] = 'n';
			break;
		case '\r':
			if (out + 2 >= dst_size)
				goto done;
			dst[out++] = '\\';
			dst[out++] = 'r';
			break;
		case '\t':
			if (out + 2 >= dst_size)
				goto done;
			dst[out++] = '\\';
			dst[out++] = 't';
			break;
		default:
			if (ch < 0x20)
				dst[out++] = ' ';
			else
				dst[out++] = ch;
			break;
		}
	}

done:
	dst[out] = '\0';
}

static size_t vled_build_json_locked(char *dst, size_t dst_size,
				     char *escaped_text, size_t escaped_size)
{
	int written;

	vled_json_escape(vled.state.text, escaped_text, escaped_size);
	written = snprintf(dst, dst_size,
			   "{\"type\":\"state\",\"width\":%d,\"height\":%d,"
			   "\"text\":\"%s\",\"color\":[%d,%d,%d],"
			   "\"brightness\":%d,\"mode\":\"%s\",\"version\":%lu}",
			   vled.state.width, vled.state.height, escaped_text,
			   vled.state.red, vled.state.green, vled.state.blue,
			   vled.state.brightness, vled.state.mode,
			   vled.state.version);
	if (written < 0)
		return 0;
	if (written >= dst_size)
		return dst_size - 1;
	return written;
}

static int vled_open(struct inode *inode, struct file *file)
{
	struct vled_file_context *ctx;

	ctx = kzalloc(sizeof(*ctx), GFP_KERNEL);
	if (!ctx)
		return -ENOMEM;

	file->private_data = ctx;
	return nonseekable_open(inode, file);
}

static int vled_release(struct inode *inode, struct file *file)
{
	kfree(file->private_data);
	file->private_data = NULL;
	return 0;
}

static ssize_t vled_read(struct file *file, char __user *user_buf,
			 size_t count, loff_t *ppos)
{
	struct vled_file_context *ctx = file->private_data;
	char *json;
	char *escaped_text;
	size_t json_len;
	ssize_t ret;

	if (!ctx)
		return -EIO;
	if (count == 0)
		return 0;

	json = kzalloc(PAGE_SIZE, GFP_KERNEL);
	if (!json)
		return -ENOMEM;

	escaped_text = kzalloc(VLED_ESCAPED_TEXT_MAX, GFP_KERNEL);
	if (!escaped_text) {
		kfree(json);
		return -ENOMEM;
	}

	mutex_lock(&vled.lock);
	json_len = vled_build_json_locked(json, PAGE_SIZE, escaped_text,
					  VLED_ESCAPED_TEXT_MAX);
	mutex_unlock(&vled.lock);

	ret = simple_read_from_buffer(user_buf, count, &ctx->read_offset, json,
				      json_len);

	kfree(escaped_text);
	kfree(json);
	return ret;
}

static ssize_t vled_write(struct file *file, const char __user *user_buf,
			  size_t count, loff_t *ppos)
{
	struct vled_file_context *ctx = file->private_data;
	char *command;
	int ret;

	if (!ctx)
		return -EIO;
	if (count == 0)
		return 0;
	if (count >= PAGE_SIZE)
		return -EMSGSIZE;

	command = memdup_user_nul(user_buf, count);
	if (IS_ERR(command))
		return PTR_ERR(command);

	vled_strip_line_end(command);

	mutex_lock(&vled.lock);
	ret = vled_apply_command_locked(command);
	if (ret == 0) {
		memset(vled.buffer, 0, sizeof(vled.buffer));
		strscpy(vled.buffer, command, sizeof(vled.buffer));
		vled.buffer_len = strlen(vled.buffer);
		ctx->write_offset += count;
	}
	mutex_unlock(&vled.lock);

	kfree(command);
	return ret == 0 ? count : ret;
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
	int ret;

	mutex_init(&vled.lock);
	vled_reset_state();

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
